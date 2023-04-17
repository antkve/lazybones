import openai
import subprocess
import time
import os

openai.api_key = os.environ["OPENAI_API_KEY"]

def get_ada_embedding(text):
    text = text.replace("\n", " ")
    return openai.Embedding.create(input=[text], model="text-embedding-ada-002")[
        "data"
    ][0]["embedding"]


def model_call(
    prompt: str,
    model: str = "gpt-3.5-turbo",
    temperature: float = 0.5,
    max_tokens: int = None,
    stop = None,
    verbose: bool = False,
    model_name_for_verbose: str = None,
):
    if verbose:
        print(f"===================== CONTEXT SENT TO {model_name_for_verbose.upper()} MODEL =====================")
        print(prompt)
        print("===================================================================================================")
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
        
            print(f"-------------------- CONTEXT RETURNED FROM {model_name_for_verbose.upper()} MODEL ----------------------")
            print(res)
            print("---------------------------------------------------------------------------------------------------------")
            return res
    