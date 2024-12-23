from flask import Flask, render_template, request
import os
import shutil
import speech_recognition as sr
from pydub import AudioSegment
from moviepy.editor import VideoFileClip
from concurrent.futures import ThreadPoolExecutor
from googletrans import Translator
from gtts import gTTS

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

LANGUAGES = {'te': 'Telugu', 'ta': 'Tamil', 'hi': 'Hindi'}

def process_audio_chunk(chunk_path):
    try:
        r = sr.Recognizer()
        audio = sr.AudioFile(chunk_path)
        with audio as source:
            audio_file = r.record(source)
            result = r.recognize_google(audio_file)
        return result
    except Exception as e:
        return str(e)

def process_audio(file_path):
    try:
        chunk_size = 60 * 1000  # 1-minute chunks in milliseconds
        audio = AudioSegment.from_wav(file_path)
        chunks = [audio[i:i + chunk_size] for i in range(0, len(audio), chunk_size)]

        chunk_paths = []
        for i, chunk in enumerate(chunks):
            chunk_path = os.path.join(app.config['UPLOAD_FOLDER'], f"chunk_{i}.wav")
            chunk.export(chunk_path, format="wav")
            chunk_paths.append(chunk_path)

        with ThreadPoolExecutor() as executor:
            results = list(executor.map(process_audio_chunk, chunk_paths))

        extracted_text = ' '.join(results) if results else ''
        translations = {}

        if extracted_text:
            translator = Translator()
            for lang_code, lang_name in LANGUAGES.items():
                translated_text = translator.translate(extracted_text, dest=lang_code).text
                translations[lang_name] = {
                    'text': translated_text,
                    'audio_path': save_audio_translation(translated_text, lang_code)
                }

        return translations, extracted_text
    except Exception as e:
        return str(e), ''

def save_audio_translation(text, lang_code):
    try:
        output_audio_path = os.path.join(app.config['UPLOAD_FOLDER'], f'TARG_AUD1_{lang_code}.mp3')
        tts = gTTS(text, lang=lang_code)
        tts.save(output_audio_path)
        return output_audio_path
    except Exception as e:
        return f"Error generating audio for {lang_code}: {e}"

def process_file(file_path):
    try:
        # Check if input is a video or audio file
        if file_path.lower().endswith(('.mp4', '.avi', '.mov', '.mkv')):
            audio_path = os.path.join(app.config['UPLOAD_FOLDER'], "converted_audio.wav")
            with VideoFileClip(file_path) as clip:
                clip.audio.write_audiofile(audio_path)
            return process_audio(audio_path)
        elif file_path.lower().endswith(('.mp3', '.wav')):
            if not file_path.endswith('.wav'):
                audio = AudioSegment.from_file(file_path)
                wav_path = file_path.replace(os.path.splitext(file_path)[1], '.wav')
                audio.export(wav_path, format='wav')
                file_path = wav_path
            return process_audio(file_path)
        else:
            return "Unsupported file format", ''
    except Exception as e:
        return str(e), ''

@app.route('/', methods=['GET', 'POST'])
@app.route('/index.html', methods=['GET', 'POST'])
def index():
    return render_template('index.html')

@app.route('/extracttext', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return render_template('index.html', message='No file part')
        
        file = request.files['file']
        
        if file.filename == '':
            return render_template('index.html', message='No selected file')
        
        if file:
            try:
                temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'temp')
                os.makedirs(temp_dir, exist_ok=True)
                temp_file_path = os.path.join(temp_dir, file.filename)
                file.save(temp_file_path)

                translations, extracted_text = process_file(temp_file_path)
                shutil.rmtree(temp_dir)

                return render_template('index.html', message='File uploaded successfully', result=extracted_text, translations=translations)
            except Exception as e:
                shutil.rmtree(temp_dir)
                return render_template('index.html', message=f'Error processing file: {e}')
    
    return render_template('index.html')

if __name__ == '__main__':
    app.run(debug=True)
