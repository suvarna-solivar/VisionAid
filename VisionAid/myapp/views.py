from django.shortcuts import render
from django.http import JsonResponse
import cv2
import os
from PIL import Image
from io import BytesIO
import requests
import pyttsx3
import google.generativeai as genai

def index(request):
    return render(request, 'index.html')

def configure_google_api(api_key):
    genai.configure(api_key=api_key)

def pil_image_to_blob(pil_image):
    byte_arr = BytesIO()
    pil_image.save(byte_arr, format='JPEG')
    return byte_arr.getvalue()

def capture_frame():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        raise RuntimeError("Failed to capture frame from webcam")
    pil_image = Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
    return pil_image

def generate_content_from_image(model, pil_image):
    image_blob = pil_image_to_blob(pil_image)
    response = model.generate_content([
        {
            "inline_data": {
                "mime_type": "image/jpeg",
                "data": image_blob
            }
        },
        {
            "text": (
               """
                Identify the only some important things that are in the image. 
                If the image contains any popular places or famous persons such as actors, 
                sports players, or singers, provide their specific names. 
                The response should only consist of the names of all objects, each name in 
                a single word without any stopwords, with correct capitalization, and without 
                any spaces, separated by commas in the image.
               """
            )
        }
    ], stream=True)

    accumulated_text = []
    for res in response:
        if res.text:
            accumulated_text.append(res.text.strip())
    
    return ' '.join(accumulated_text)

def fetch_from_knowledge_graph(query, api_key):
    api_endpoint = "https://kgsearch.googleapis.com/v1/entities:search"
    params = {
        "query": query,
        "key": api_key
    }
    response = requests.get(api_endpoint, params=params)
    return response.json()

def display_knowledge_graph_data(data, query, fallback_model):
    unique_names = set()
    
    if "itemListElement" in data:
        for item in data["itemListElement"]:
            name = item["result"]["name"]
            if name.lower() == query.lower() and name not in unique_names:
                item_image = item["result"].get("image", {}).get("contentUrl", "No image available")
                description = item["result"].get("detailedDescription", {}).get("articleBody", None)
                detailed_description = item["result"].get("detailedDescription", {}).get("url", None)
                unique_names.add(name)
                return {
                    "Name": name,
                    "Description": description,
                    "Detailed Description": detailed_description,
                }
    
    response = fallback_model.generate_content(f"Give me a description of 60 words about {query}")
    description = response.text if response.text else "No description available"
    detailed_description = f"https://en.wikipedia.org/wiki/{query.replace(' ', '_')}"
    return {
        "Name": query,
        "Description": description,
        "Detailed Description": detailed_description,
    }

def preprocess_object_name(name):
    name_mapping = {}
    return name_mapping.get(name.lower(), name)


def read_out_descriptions(descriptions, detected_objects):
    engine = pyttsx3.init(driverName='espeak')

    # Read out detected objects
    detected_objects_text = "Detected objects: " + ', '.join(detected_objects)
    print(detected_objects_text)
    engine.say(detected_objects_text)

    # Read out descriptions
    for desc in descriptions:
        text_to_read = f"{desc['Name']}: {desc['Description']}"
        print(text_to_read)
        engine.say(text_to_read)

    engine.runAndWait()


def capture_frame_view(request):
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY environment variable not set")
    configure_google_api(api_key)

    pil_image = capture_frame()
    model = genai.GenerativeModel('gemini-1.5-pro-latest')
    response_text = generate_content_from_image(model, pil_image)

    object_names = [name.strip() for name in response_text.split(',')]
    print("Detected objects:", object_names)

    fallback_model = genai.GenerativeModel('gemini-pro')
    descriptions = []

    for object_name in object_names:
        preprocessed_name = preprocess_object_name(object_name)
        data = fetch_from_knowledge_graph(preprocessed_name, api_key)
        description = display_knowledge_graph_data(data, preprocessed_name, fallback_model)
        descriptions.append(description)


    # read_out_descriptions(descriptions,object_names)
    
    return JsonResponse({
        'detected_objects': object_names,
        'descriptions': descriptions
    }, safe=False)


