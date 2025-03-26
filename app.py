from flask import Flask, request, jsonify, send_file, url_for
from flask_cors import CORS 
import os
import ffmpeg
import speech_recognition as sr
from pydub import AudioSegment
from deep_translator import GoogleTranslator
from gtts import gTTS

app = Flask(__name__)
CORS(app) 

# Set up upload and processed folders
UPLOAD_FOLDER = "uploads"
PROCESSED_FOLDER = "processed"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)

@app.route('/process', methods=['POST'])
def process_video():
    try:
        if 'video' not in request.files:
            return jsonify({"error": "No video file provided"}), 400
        
        video_file = request.files['video']
        target_language = request.form.get('language', 'en')  # Default to English

        video_filename = "input_video.mp4"
        video_path = os.path.join(UPLOAD_FOLDER, video_filename)
        video_file.save(video_path)

        print(f"✅ Video saved at: {video_path}")

        # Define output file paths
        audio_path = os.path.join(PROCESSED_FOLDER, "extracted_audio.mp3")
        wav_path = os.path.join(PROCESSED_FOLDER, "extracted_audio.wav")
        translated_audio_path = os.path.join(PROCESSED_FOLDER, "translated_audio.mp3")
        video_without_audio = os.path.join(PROCESSED_FOLDER, "video_no_audio.mp4")
        final_video_path = os.path.join(PROCESSED_FOLDER, "final_video.mp4")

        # Extract audio from video
        ffmpeg.input(video_path).output(audio_path, format='mp3', acodec='libmp3lame').run(overwrite_output=True, quiet=True)
        print(f"✅ Audio extracted: {audio_path}")

        # Convert MP3 to WAV for speech recognition
        audio = AudioSegment.from_mp3(audio_path)
        audio.export(wav_path, format="wav")
        print(f"✅ MP3 converted to WAV: {wav_path}")

        # Perform speech recognition on the WAV file
        recognizer = sr.Recognizer()
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)
        text = recognizer.recognize_google(audio_data)
        print(f"✅ Transcription: {text}")

        # Translate the transcribed text
        translated_text = GoogleTranslator(source='auto', target=target_language).translate(text)
        print(f"✅ Translated Text: {translated_text}")

        # Convert translated text to speech
        tts = gTTS(text=translated_text, lang=target_language)
        tts.save(translated_audio_path)
        print(f"✅ Translated audio saved: {translated_audio_path}")

        # Remove the original audio from the video
        ffmpeg.input(video_path).output(video_without_audio, an=None, vcodec='copy').run(overwrite_output=True)
        print(f"✅ Video without audio created: {video_without_audio}")

        # Merge translated audio with video
        video = ffmpeg.input(video_without_audio)
        audio = ffmpeg.input(translated_audio_path)
        ffmpeg.output(video, audio, final_video_path, vcodec='copy', acodec='aac').run(overwrite_output=True, quiet=True)
        print(f"✅ Final video created: {final_video_path}")

        if not os.path.exists(final_video_path):
            print(f"❌ Final video not found: {final_video_path}")
            return jsonify({"error": "Final video creation failed. File not found."}), 500

        print("✅ Sending response to client with download link.")
        return jsonify({
            "message": "Processing complete!",
            "original_text": text,  # 
            "translated_text": translated_text, 
            "download_url": url_for('download_file', filename="final_video.mp4", _external=True)
})

    except Exception as e:
        print(f"❌ General Processing Error: {e}")
        return jsonify({"error": f"Processing failed: {str(e)}"}), 500

@app.route('/download/<filename>')
def download_file(filename):
    file_path = os.path.join(PROCESSED_FOLDER, filename)
    if os.path.exists(file_path):
        return send_file(file_path, as_attachment=True)
    else:
        return jsonify({"error": "File not found."}), 404

if __name__ == '__main__':
    app.run(debug=True)
