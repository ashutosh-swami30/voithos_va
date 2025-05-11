import customtkinter as ctk
import threading
import numpy as np
import string
import os
import whisper
import sounddevice as sd
import pyttsx3
import torch
import requests
import webbrowser
import json
from tqdm import tqdm
from concurrent.futures import ThreadPoolExecutor

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

class Voithos:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.model = whisper.load_model("medium")
        self.sample_rate = 16000
        self.recording_duration = 4
        self.should_exit = False

    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()

    def listen_and_respond(self):
        try:
            duration = self.recording_duration
            recording = sd.rec(int(duration * self.sample_rate), samplerate=self.sample_rate, channels=1, dtype='float32')
            sd.wait()
            audio = np.squeeze(recording)
            res = self.model.transcribe(audio, language='english', fp16=torch.cuda.is_available())
            user_input = res["text"].lower().strip()
            user_input = user_input.translate(str.maketrans('', '', string.punctuation))
            if user_input in ['exit', 'quit', 'bye', 'end', 'goodbye', 'seeyou']:
                self.speak("Goodbye!")
                self.should_exit = True
                return "Goodbye!"
            response = self.generate_response(user_input)
            self.speak(response)
            return f"You: {user_input}\nVoithos: {response}"
        except Exception as e:
            self.speak("Sorry, I couldn't understand what you said.")
            return f"Error: {e}"

    def set_recording_duration(self, seconds):
        try:
            seconds = int(seconds)
            if 1 <= seconds <= 30:
                self.recording_duration = seconds
                return f"Recording duration set to {seconds} seconds."
            return "Duration must be between 1 and 30 seconds."
        except ValueError:
            return "Invalid duration."

    def web_search(self, query):
        url = f"https://api.duckduckgo.com/?q={query}&format=json"
        try:
            response = requests.get(url, timeout=10)
            data = response.json()
            results = data.get("RelatedTopics", [])
            return results
        except requests.RequestException:
            return []

    def generate_response(self, user_input):
        if any(greeting in user_input for greeting in ['hello', 'hi', 'namaste']):
            return "Hello! How can I assist you?"
        elif "open file" in user_input:
            file_name = user_input.split("open file")[-1].strip()
            return self.open_file(file_name)
        elif "open" in user_input:
            site = user_input.split("open")[-1].strip()
            return self.open_website(site)
        elif "set recording time" in user_input:
            words = user_input.split()
            for word in words:
                if word.isdigit():
                    return self.set_recording_duration(word)
            return "Please specify the duration to be set for recording"
        elif "search for" in user_input:
            query = user_input.split("search for")[-1].strip()
            results = self.web_search(query)
            if results:
                response = f"Results for '{query}':\n"
                for result in results[:5]:
                    response += f"- {result['Text']} ({result['FirstURL']})\n"
                return response
            return f"No results found for '{query}'."
        else:
            return "I'm sorry, I didn't understand that."

    def get_available_drives(self):
        drives = []
        for drive in string.ascii_uppercase:
            if os.path.exists(f"{drive}:\\"):
                drives.append(f"{drive}:\\")
        return drives

    def build_file_index(self, drives=None, index_path="file_index.json"):
        if drives is None:
            drives = self.get_available_drives()
        file_index = {}
        excluded_dirs = ["Windows", "Program Files", "Program Files (x86)", "ProgramData", "AppData"]

        def process_drive(drive):
            drive_index = {}
            try:
                for root, dirs, files in os.walk(drive):
                    dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('$')]
                    for name in files + dirs:
                        key = name.lower()
                        full_path = os.path.join(root, name)
                        drive_index.setdefault(key, []).append(full_path)
            except Exception as e:
                print(f"Error processing {drive}: {e}")
            return drive_index

        with ThreadPoolExecutor(max_workers=len(drives)) as executor:
            results = list(executor.map(process_drive, drives))
        for index in results:
            for key, paths in index.items():
                file_index.setdefault(key, []).extend(paths)
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(file_index, f)

    def find_in_index(self, file_name, index_path="file_index.json"):
        file_name = file_name.lower()
        try:
            with open(index_path, "r", encoding='utf-8') as f:
                file_index = json.load(f)
            matches = [path for key, paths in file_index.items() if file_name in key for path in paths]
            return matches
        except FileNotFoundError:
            return []

    def open_file(self, file_name):
        matches = self.find_in_index(file_name)
        if matches:
            path = matches[0]
            if os.name == 'nt':
                os.startfile(path)
            else:
                os.system(f"xdg-open '{path}'")
            return f"Opening {file_name}"
        return f"File '{file_name}' not found."

    def open_website(self, site):
        site = site.strip().lower().replace(" ", "")
        if '.' in site:
            url = f"https://{site}"
            try:
                requests.head(url, timeout=3)
                webbrowser.open(url)
                return f"Opening {url}"
            except:
                return f"{site} not reachable"
        domain_variants = [".com", ".org", ".net", ".in", ".io"]
        for domain in domain_variants:
            url = f"https://www.{site}{domain}"
            try:
                requests.head(url, timeout=3)
                webbrowser.open(url)
                return f"Opening {url}"
            except:
                continue
        return "No valid domain found."


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Voithos Voice Assistant")
        self.geometry("700x520")
        self.voithos = Voithos()

        self.output_box = ctk.CTkTextbox(self, width=680, height=350)
        self.output_box.pack(pady=10)

        self.listen_button = ctk.CTkButton(self, text="🎤 Start Listening", command=self.start_listening)
        self.listen_button.pack(pady=10)

        self.status_label = ctk.CTkLabel(self, text="", text_color="orange")
        self.status_label.pack(pady=2)

        self.duration_entry = ctk.CTkEntry(self, placeholder_text="Set Recording Duration (1-30 sec)")
        self.duration_entry.pack(pady=5)

        self.set_duration_button = ctk.CTkButton(self, text="Set Duration", command=self.set_duration)
        self.set_duration_button.pack(pady=5)

    def start_listening(self):
        self.status_label.configure(text="Processing...")
        self.listen_button.configure(state="disabled")
        self.output_box.insert(ctk.END, "\nListening...\n")
        threading.Thread(target=self.process_audio).start()

    def process_audio(self):
        result = self.voithos.listen_and_respond()
        self.output_box.insert(ctk.END, f"{result}\n")
        self.status_label.configure(text="")
        self.listen_button.configure(state="normal")

    def set_duration(self):
        seconds = self.duration_entry.get()
        result = self.voithos.set_recording_duration(seconds)
        self.output_box.insert(ctk.END, f"{result}\n")


if __name__ == "__main__":
    app = App()
    app.mainloop()
