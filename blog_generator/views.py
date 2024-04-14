import json
import os

import assemblyai as aai
import openai
from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import redirect
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from pytube import YouTube

from .models import BlogPost

# Create your views here.


def index(request):
    return render(request, "blog_generator/index.html")


@csrf_exempt
def generate_blog(request):
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            yt_link = data["link"]
        except (KeyError, json.JSONDecodeError):
            return JsonResponse({"error": "invalid data sent"}, status=400)

        title = yt_title(yt_link)

        transcription = get_transcription(yt_link)
        if not transcription:
            return JsonResponse({"error": "Failed to get transcript"}, status=500)

        blog_content = generate_blog_from_transcription(transcription)
        if not blog_content:
            return JsonResponse(
                {"error": "Failed to generate blog article"},
                status=500,
            )

        new_blog_article = BlogPost.objects.create(
            user=request.user,
            youtube_title=title,
            youtube_link=yt_link,
            generated_content=blog_content,
        )
        new_blog_article.save()

        return JsonResponse({"content": blog_content})
    else:
        return JsonResponse({"error": "invalid request method"}, status=405)


def yt_title(link):
    yt = YouTube(link)
    title = yt.title
    return title


def download_audio(link):
    yt = YouTube(link)
    video = yt.streams.filter(only_audio=True).first()
    out_file = video.download(output_path=settings.MEDIA_ROOT)
    base, ext = os.path.splitext(out_file)
    new_file = base + ".mp3"
    os.rename(out_file, new_file)
    return new_file


def get_transcription(link):
    audio_file = download_audio(link)
    aai.settings.api_key = settings.ASSEMBLYAI_KEY

    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_file)

    return transcript.text


def generate_blog_from_transcription(transcription):
    openai.api_key = settings.OPENAI_KEY
    prompt = f"Based on the following trancription of a youtube video, write a comprehensive articel, \
    write it based on the transcript,  but dont make it look like a youtube video, make it look \
    like a proper blog article :\n\n {transcription}\n\nArticle:"

    response = openai.completions.create(
        model="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=100,
    )

    generated_content = response.choices[0].text.strip()

    return generated_content


def blog_list(request):
    blog_articles = BlogPost.objects.filter(user=request.user)
    return render(
        request,
        "blog_generator/all-blogs.html",
        {"blog_articles": blog_articles},
    )


def blog_details(request, pk):
    blog_article_detail = BlogPost.objects.get(id=pk)
    if request.user == blog_article_detail.user:
        return render(
            request,
            "blog_generator/blog-details.html",
            {"blog_article_detail": blog_article_detail},
        )
    return redirect("/")
