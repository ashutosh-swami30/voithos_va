import whisper
#import tempfile
import numpy as np
import pyttsx3
import webbrowser
import requests
from setuptools import setup
import os
import sounddevice as sd
import torch
#import scipy.io.wavfile
import json
import string
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
import threading
from tqdm import tqdm

#Main class
class Voithos:
    def __init__(self):
        self.engine = pyttsx3.init()
        self.model = whisper.load_model("base")
        self.sample_rate = 16000 #Whisper expects 16KHz audio
        self.recording_duration = 4
    
    #To record the voice input
    def set_recording_duration(self, seconds):
        try:
            seconds = int(seconds)
            if seconds < 1:
                return "Duration must be at least 1 second."
            if seconds > 30:
                return "Duration cannot exceed 30 seconds."
            
            self.recording_duration = seconds
            return f"Recording duration set to {seconds} seconds."
        except ValueError:
            return "Please provide a valid number of seconds."

    
    #Audio recog done here
    def listen_and_respond(self):
        try:
            print("Listening....")
            duration = self.recording_duration
            recording = sd.rec(int(duration * self.sample_rate), samplerate = self.sample_rate, channels=1, dtype='float32')
            sd.wait()
            audio = np.squeeze(recording)
            
            print("Processing.....")
            res = self.model.transcribe(audio, language='english' , fp16 = torch.cuda.is_available())
            user_input = res["text"].lower().strip()
            
            print("You:",user_input)
            if user_input in ['exit','quit','bye','end']:
                self.speak("Goodbye!")
                return "Goodbye!"
            response = self.generate_response(user_input)
            print("Voithos:", response)
            self.speak(response)
            return response
        except Exception as e:
            print(f"An error occurred: {e}")
            self.speak("Sorry, I couldn't understand what you said.")
            return ""
        
    #Audio output
    def speak(self, text):
        self.engine.say(text)
        self.engine.runAndWait()
    
    #web search function
    def web_search(self, query):
        url = f"https://api.duckduckgo.com/?q={query}&format=json"
        try:
            response = requests.get(url,timeout=10)
            data = response.json()
            results = data.get("RelatedTopics", [])
            return results
        except requests.RequestException as e:
            print(f"Error fetching results: {e}")
            return []
        
    #generates response
    def generate_response(self, user_input):
        if any(greeting in user_input for greeting in ['hello', 'hi', 'namaste']):
            return "Hello! How can I assist you?"
        
        #Opens a file within the OS
        elif "open file" in user_input:
            file_name = user_input.split("open file")[-1].strip()
            return self.open_file(file_name)
        
        #Opens any website
        elif "open" in user_input:
            site = user_input.split("open")[-1].strip()
            return self.open_website(site)

        #Sets recording time for voice input
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
                response = f"Here are some results for '{query}':\n"
                for result in results[:5]:  # Limiting to first 5 results for brevity
                    response += f"- {result['Text']} ({result['FirstURL']})\n"
                return response
            else:
                return f"No results found for '{query}'." 
        else:
            return "I'm sorry, I didn't understand that."
    
    
    # Opens a website by attempting to construct a valid URL
    def open_website(self,site):
        
        site = site.strip().lower().replace(" ", "")
        if '.' in site:
            url = f"https://{site}"
            try:
                response = requests.head(url, timeout=3)
                if response.status_code < 400:
                    webbrowser.open(url)
                    return f"Opening {url}"
            except requests.RequestException:
                return f"Sorry, {site} doesn't seem reachable."
        
        domain_variants = [".com",".org", ".net", ".in", ".io", ".ai",".to",".jp",".us",".uk"]
        for domain in domain_variants:
            url = f"https://www.{site}{domain}"
            try:
                response = requests.head(url,timeout=3)
                if response.status_code < 400:
                    webbrowser.open(url)
                    return f"Opening {url}"
            except requests.RequestException:
                continue
        return f"Sorry, I couldnt find a valid domain for the specified website"
    

    #get available drives
    def get_available_drives(self):
        drives = []
        for drive in string.ascii_uppercase:
            if os.path.exists(f"{drive}:\\"):
                drives.append(f"{drive}:\\")
        return drives
    
    #allows users to select which drive to search in
    def prompt_user_for_drives(self):
        available_drives = self.get_available_drives()
        print("Available drives are:", ", ".join(available_drives))
        self.speak("Available drives are "+ ", ".join(available_drives))
        
        
    
    #build index for file search, optimizes the speed
    def build_file_index(self, drives=None, index_path="file_index.json"):
        if drives is None:
            drives = self.get_available_drives()
        file_index = {}
        excluded_dirs = ["Windows", "Program Files", "Program Files (x86)", "ProgramData", "AppData"]
        
        def process_drive(drive):
            drive_index = {}
            try:
                print(f"Indexing drive: {drive}")
                file_list = []
                for root, dirs, files in os.walk(drive):
                    dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('$')]
                    file_list.append((root, files, dirs))
                    
                for root, files, dirs in tqdm(file_list, desc=f"{drive}"):
                    for name in files + dirs: 
                        key = name.lower()
                        full_path = os.path.join(root, name)
                        drive_index.setdefault(key, []).append(full_path)
            except Exception as e:
                print(f"Error processing {drive}:{e}")
            return drive_index
        
        
        with ThreadPoolExecutor(max_workers=len(drives)) as executor:
            results = list(executor.map(process_drive,drives))
        
        for index in results:
            for key, paths in index.items():
                file_index.setdefault(key, []).extend(paths)
                
        with open(index_path, "w", encoding="utf-8") as f:
            json.dump(file_index, f)
        print(f"File index built with {len(file_index)} unique names.")
            
        '''for drive in drives:
            print(f"Indexing drive: {drive}")
            for root, dirs, files in os.walk(drive):
                #skips system folders
                dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith('$')]
                
                for name in files + dirs: 
                    key = name.lower()
                    full_path = os.path.join(root, name)
                    file_index.setdefault(key, []).append(full_path)'''
        
    #finds the file in the index
    def find_in_index(self, file_name, index_path="file_index.json"):
        file_name = file_name.lower()
        try:
            with open(index_path, "r", encoding='utf-8') as f:
                file_index = json.load(f)
            matches = [path for key, paths in file_index.items() if file_name in key for path in paths]
            return matches
        except FileNotFoundError:
            return []
    
    #Opens a file from the indexed file pool
    def open_file(self, file_name):
        print(f"Trying to open: {file_name}")
        try:
            matches = self.find_in_index(file_name)
            if matches:
                path = matches[0]
                if os.name =='nt': #for windows
                    os.startfile(path)
                else:
                    os.system(f"xdg-open '{path}'")
                return f"Opening {file_name}"
            else:
                return f"Sorry, I couldn't find the file {file_name}."
        except Exception as e:
            print(f"An error occurred: {e}")
            return f"Sorry, I couldn't open the file {file_name}."
    
    
    

voithos = Voithos()
if not os.path.exists("file_index.json"):
    print("Building file index... This may take a few minutes.")
    voithos.build_file_index()

    
while True:
    response = voithos.listen_and_respond()
    if response == "Goodbye!":
        break
        
        