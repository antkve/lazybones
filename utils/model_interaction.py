import openai
import subprocess
import time
import os
import dotenv
import argparse


dotenv.load_dotenv()

openai.api_key = os.environ["OPENAI_API_KEY"]

def get_ada_embedding(text):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input=[text], model="text-embedding-ada-002")[
        "data"
    ][0]["embedding"]

def edit_call(
    input_text: str,
    prompt: str,
    model: str = "text-davinci-edit-001",
    temperature: float = 0.5,
    verbose: bool = False,
    model_name_for_verbose: str = None,
):
    if verbose:
        print(f"===================== CONTEXT SENT TO {model_name_for_verbose.upper()} AGENT =====================")
        print(input_text)
        print(prompt)
        print("===================================================================================================")
    while True:
        try:
            response = openai.Edit.create(
            model=model,
            input = input_text,
            instruction=prompt,
            temperature = temperature,
            )
            res = response.choices[0].text.strip()
        except openai.error.RateLimitError:
            print(
                "The OpenAI API rate limit has been exceeded. Waiting 10 seconds and trying again."
            )
            time.sleep(10)
        else:
            print(f"-------------------- CONTEXT RETURNED FROM {model_name_for_verbose.upper()} AGENT ----------------------")
            print(res)
            print("---------------------------------------------------------------------------------------------------------")
            return res

def log(message):
    with open("log.txt", "a", encoding='utf-8') as f:
        f.write(message + '\n')

def printlog(message):
    print(message)
    log(message)

def model_call(
    prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.5,
    max_tokens: int = None,
    stop = None,
    suffix: str = None,
    verbose: bool = True,
    quiet: bool = False,
    model_name_for_verbose: str = None,

):
    if verbose:
        printlog(f"===================== CONTEXT SENT TO {model_name_for_verbose.upper()} AGENT =====================")
        printlog(prompt)
        printlog("===================================================================================================")
    else:
        log(f"===================== CONTEXT SENT TO {model_name_for_verbose.upper()} AGENT =====================")
        log(prompt)
        log("===================================================================================================")
    while True:
        try:
            if model.startswith("llama"):
                # Spawn a subprocess to run llama.cpp
                cmd = ["llama/main", "-p", prompt]
                result = subprocess.run(cmd, shell=True, stderr=subprocess.DEVNULL, stdout=subprocess.PIPE, text=True)
                res = result.stdout.strip()
            elif not model.startswith("gpt-"):
                # Use completion API
                response = openai.Completion.create(
                    engine=model,
                    prompt=prompt,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=1,
                    frequency_penalty=0,
                    presence_penalty=0,
                    suffix = suffix,
                    stop=stop,
                )
                res = response.choices[0].text.strip()
            else:
                # Use chat completion API
                messages = [{"role": "system", "content": prompt}]
                response = openai.ChatCompletion.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    n=1,
                    stop=None,
                )
                res = response.choices[0].message.content.strip()
        except openai.error.RateLimitError:
            print(
                "The OpenAI API rate limit has been exceeded. Waiting 10 seconds and trying again."
            )
            time.sleep(10)  # Wait 10 seconds and try again
        else:
            if not quiet:
                printlog(f"------------------------ CONTEXT RETURNED FROM {model_name_for_verbose.upper()} AGENT --------------------------")
                printlog(res)
                printlog("---------------------------------------------------------------------------------------------------------")
            else:
                log(f"------------------------ CONTEXT RETURNED FROM {model_name_for_verbose.upper()} AGENT --------------------------")
                log(res)
                log("---------------------------------------------------------------------------------------------------------")
            return res
    