from google import genai
from google.genai import types
import base64

def generate():
    client = genai.Client(
        vertexai=True,
        project="gothic-guard-459415-q5",
        location="global",
    )

    msg1_video1 = types.Part.from_uri(
        file_uri="https://youtu.be/W-csPZKAQc8",
        mime_type="video/*",
    )
    msg1_text1 = types.Part.from_text(text="""Please write a 40 character long intriguing title of this video and 10 comma separated hashtags that will be used for youtube shorts. Format the response as a python dictionary {\"Description\": title of video(not more than 50 characters), \"Keywords\": comma separated hashtags(10)}""")
    msg2_text1 = types.Part.from_text(text="""```json
{\"Description\": \"Cosmic Dance: Galaxies Collide\", \"Keywords\": \"galaxy,collision,space,astronomy,stars,nebula,universe,simulation,science,cosmos\"}
```""")
    msg3_text1 = types.Part.from_text(text="""This image features a vibrant 3D animated character named \"Lafufu,\" looks just like a labubu who is a playful, cartoonish monster toy lookalike with large, expressive eyes . Lafufu is wearing a red jacket and leggings that glow with digital, glitchy patterns, striking an energetic dance pose reminiscent of Michael Jackson's \"Thriller.\" Around Lafufu,  is a real labubu  dancer with several other characters are seen as transparent, digitally-glowing outlines, also dancing  with glowing neon blue and purple lights, creating a dynamic, club-like atmosphere. Social media icons (Instagram, TikTok, YouTube, X/Twitter, Snapchat) are subtly incorporated into the stage as glowing holograms, with a prominent YouTube play button in the foreground. Above Lafufu, the text \"THE LAFUFU WAY\" is displayed in glowing blue. Below the character, the text \"AI VIRAL CONTENT IO\" is visible, followed by the tagline \"UNLEASH YOUR INNER VIRAL THRILLER!\" The overall style is playful, futuristic, and aimed at a viral, high-energy appeal.""")

    model = "gemini-2.5-flash-lite"
    contents = [
        types.Content(
            role="user",
            parts=[
                msg1_video1,
                msg1_text1
            ]
        ),
        types.Content(
            role="model",
            parts=[
                msg2_text1
            ]
        ),
        types.Content(
            role="user",
            parts=[
                msg3_text1
            ]
        ),
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature = 1,
        top_p = 0.95,
        max_output_tokens = 65535,
        safety_settings = [types.SafetySetting(
            category="HARM_CATEGORY_HATE_SPEECH",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_DANGEROUS_CONTENT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
            threshold="OFF"
        ),types.SafetySetting(
            category="HARM_CATEGORY_HARASSMENT",
            threshold="OFF"
        )],
        thinking_config=types.ThinkingConfig(
            thinking_budget=0,
        ),
    )

    for chunk in client.models.generate_content_stream(
        model = model,
        contents = contents,
        config = generate_content_config,
        ):
        print(chunk.text, end="")

generate()
