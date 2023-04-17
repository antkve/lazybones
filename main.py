import os
import unittest

import dotenv
dotenv.load_dotenv()
import re
from utils import model_interaction
import subprocess
from local import LocalCache
import tools.browsing

print(str(tools.browsing.google_search("netflix ticker symbol")))

#codebase_memory = LocalCache("CodebaseMemory")
all_codebase_signatures = {} # {filename: [signature1, signature2, ...], ...}
all_pinecone_memory = LocalCache("ActionsMemory")
all_memory = []

INITIAL_PLANNING_AGENT_PROMPT_FORM = """
ENVIRONMENT:
{environment}

GOAL:
{goal}.

CONSTRAINTS:
Final product must have thorough test coverage. Do not use git or any other version control system.

TASK LIST FORMAT:
Task 1. <Task name>: <Task description>
Task 2. <Task name>: <Task description>
...

FULL TASK LIST:
"""

SUBTASKER_PROMPT_FORM = """
ENVIRONMENT:
{environment}

GOAL:
{goal}

CURRENT TASK LIST:
{task_list}

CONSTRAINTS:
Final product must have thorough test coverage. Do not use git or any other version control system.

CURRENT TASK:
Task {task_number}. {task_name}: {task_description}

SUBTASK LIST FORMAT:
Subtask 1. <Subtask name>: <Subtask description>
Subtask 2. <Subtask name>: <Subtask description>

TASK {task_number} SUBTASKS:
"""

SUBTASK_SUBTASKER_PROMPT_FORM = """
ENVIRONMENT:
{environment}

GOAL:
{goal}

CURRENT TASK LIST:
{task_list}

CONSTRAINTS:
Final product must have thorough test coverage. Do not use an IDE. Do not use git, or any other version control system.

CURRENT TASK:
Task {task_number}. {task_name}: {task_description}

SUBTASK LIST FORMAT:
Subtask 1. <Subtask name>: <Subtask description>

TASK {task_number} SUBTASKS:
"""

SUBTASK_CATEGORIZER_PROMPT_FORM = """
ENVIRONMENT:
{environment}

FINAL GOAL:
{goal}

CURRENT GOAL:
{current_task}

TASK LIST:
{subtask_list}

CONSTRAINTS:
Final product must have thorough test coverage. Do not use git or any other version control system.


CURRENT TASK:
Task {subtask_number}. {subtask_name}: {subtask_description}

These are the categories of work that can be done on a task:

(1) Writing code
(2) Terminal command or sequence of terminal commands
(3) Research
(4) Other

Which of these categories best describes the action(s) needed for the current task?
If it involves multiple categories, list them all.
Make sure your answer includes the number of the category you choose, in parentheses as above, e.g. (2)

ANSWER:"""


RELEVANT_CODE_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

CURRENT SUBTASK:
{current_subtask}

These are signatures of some of the files, functions and classes in the codebase:

{codebase_signatures}

Write the signatures of the functions and classes in the codebase most relevant to the current task and subtask, if there are any.
If there are no relevant functions or classes, write "None".
Make sure to write them in the same format they are in above, with the filename followed by the functions/classes.

RESPONSE:
"""

SUPERVISOR_ADVICE_PROMPT_FORM = """

ENVIRONMENT:
{environment}

=== FORM 1 ===

FINAL GOAL:
Create a binary calculator program in python.

CURRENT TASK:
Write arithmetic functions: Write some python functions for doing arithmetic on binary strings.

CURRENT SUBTASK:
Write test for add_two_numbers: Write a test for the add_two_numbers function in the utils.py file.

RECENT ACTIONS:
- I wrote some comments in main.py
- I wrote the following functions/classes in binary_arithmetic.py: add_two_numbers(a, b), subtract_two_numbers(a, b), multiply_two_numbers(a, b), divide_two_numbers(a, b)

RELEVANT LONG-TERM MEMORIES:
- I wrote the following functions/classes in binary_arithmetic.py: BinaryString(str) add_two_numbers(a, b), subtract_two_numbers(a, b), multiply_two_numbers(a, b), divide_two_numbers(a, b)
- I ran the following commands: 
- I installed python and unittest

MESSAGE:
I need you to write a test for the binary add_two_numbers function, which I've written in utils.py. The test should include at least 5 test cases,
and should be in a file called utils_test.py. It should use the unittest module.

=== FORM 2 ===

FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

CURRENT SUBTASK:
{current_subtask}

RECENT ACTIONS:
{recent_actions}

RELEVANT LONG-TERM MEMORIES:
{long_term_memories}

MESSAGE:
"""


WRITE_CODE_PROMPT_FORM = """
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

EXISTING FUNCTIONS/CLASSES:
{relevant_code}

SUPERVISOR_ADVICE:
{supervisor_advice}

Using the above goal, code snippets and advice, write python code to perform the following subtask:
{subtask_string}

You may use any functions or classes from the codebase, or write new ones. Make sure your code is compatible with the existing codebase.
Your response should be in the following format:

File: <filename>.py
Code:
<code>

If there are multiple files to be written to, separate them with a line of dashes.
Your code should be a complete solution; do not leave any TODOs or temporary code.
Each function must specify its return type using a type hint.

COMPLETED CODE:
"""


EXECUTE_COMMANDS_PROMPT_FORM = r"""
ENVIRONMENT:
{environment}

Run commands to accomplish the current subtask, based on the information given.
Run SUCCESS if your commands have been successful, and FAIL if they are not. Run FAIL if you try something multiple times without success.

=== PROBLEM 1 ===
FINAL GOAL:
Create a binary calculator program in python.

CURRENT TASK:
Write arithmetic functions: Write python functions for doing arithmetic on binary strings representing integers.

CURRENT SUBTASK:
Run the test: Run the tests for the arithmetic functions in the src/binary_arithmetic.py file.

EXISTING FUNCTIONS/CLASSES:
src/binary_arithmetic.py:
    - BinaryString(str)
    - add_two_numbers(a, b)
    - subtract_two_numbers(a, b)
    - multiply_two_numbers(a, b)
src/test_binary_arithmetic.py:
    - TestBinaryString(unittest.TestCase)
    - TestAddTwoNumbers(unittest.TestCase)
    - TestSubtractTwoNumbers(unittest.TestCase)
    - TestMultiplyTwoNumbers(unittest.TestCase)

src/utils.py:
    - binary_to_int(binary_string) -> int
    - int_to_binary(integer) -> BinaryString

SUPERVISOR_ADVICE:
I need you to run the tests for the binary arithmetic functions. The tests are in src/test_binary_arithmetic.py.

>>>>>>>>>>>> START TRIAL 1 <<<<<<<<<<<<
EXECUTOR THOUGHTS:
I need to run the tests to make sure the functions are working correctly.
COMMAND:
python -m unittest src/test_binary_arithmetic.py
EXECUTENOW
OUTPUT:
E
======================================================================
ERROR: main (unittest.loader._FailedTest)
----------------------------------------------------------------------
ImportError: Failed to import test module: main
Traceback (most recent call last):
  File "C:\Program Files\WindowsApps\PythonSoftwareFoundation.Python.3.8_3.8.2800.0_x64__qbz5n2kfra8p0\lib\unittest\loader.py", line 
154, in loadTestsFromName
    module = __import__(module_name)
  File "C:\Users\abk\Documents\git\lazybones\main.py", line 3, in <module>
    import numpy as np
ModuleNotFoundError: No module named 'numpy'


----------------------------------------------------------------------
Ran 1 test in 0.000s

FAILED (errors=1)

EXECUTOR THOUGHTS:
I failed to run the tests because I don't have numpy installed. I should run FAIL.
COMMAND:
FAIL
EXECUTENOW

>>>>>>>>>>>> START TRIAL 2 <<<<<<<<<<<<
EXECUTOR THOUGHTS:
In the last trial, I failed to run the tests because I don't have numpy installed. I should install numpy.
COMMAND:
pip install numpy
EXECUTENOW
OUTPUT:
Collecting numpy
  Downloading numpy-1.20.2-cp38-cp38-win_amd64.whl (13.7 MB)
     |████████████████████████████████| 13.7 MB 1.1 MB/s
Installing collected packages: numpy
Successfully installed numpy-1.20.2

EXECUTOR THOUGHTS:
I have installed numpy. I should run the tests again.
COMMAND:
python -m unittest src/test_binary_arithmetic.py
EXECUTENOW
OUTPUT:
.
----------------------------------------------------------------------
Ran 1 test in 0.000s

OK

EXECUTOR THOUGHTS:
I successfully ran the tests. I should run SUCCESS.
COMMAND:
SUCCESS

=== PROBLEM 2 ===
FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

CURRENT SUBTASK:
{current_subtask}

EXISTING FUNCTIONS/CLASSES:
{relevant_code}

SUPERVISOR ADVICE:
{supervisor_advice}

EXECUTOR THOUGHTS:
"""

FAILURE_RECOVERY_PROMPT_FORM = """
ENVIRONMENT:
{environment}

FINAL GOAL:
{goal}

TASK LIST:
{task_list}

CURRENT TASK:
{current_task}

RELEVANT FUNCTIONS/CLASSES:
{relevant_code}

So far, you have been {category_of_work} in order to accomplish the current task, but you have been unsuccessful.
Your actions and the results of those actions are listed below.

{agent_actions_and_results}

"""


RESEARCH_PROMPT_FORM = """
AVAILABLE COMMANDS:
GOOGLE: <search query>
SUMMARIZE: <url> <question to answer when summarizing>
SUMMARIZEALL: <url>
SUCCESS: <message to supervisor with all relevant information you have gathered>
FAIL: <reason for failure>

=== RESEARCH PROBLEM 1 ===

FINAL GOAL:
Analyze the stock prices of every public company with a market cap of over $10 billion.

CURRENT TASK:
Research the stock market: Research each of the list of companies I have retrieved.

CURRENT SUBTASK:
Find Netflix ticker: Find the ticker symbol for Netflix.

SUPERVISOR ADVICE:
I need you to find the ticker symbol for Netflix. You can use Google to find the ticker symbol.

>>>>>>>>>>>> START TRIAL 1 <<<<<<<<<<<<

RESEARCHER THOUGHTS:
I need to find the ticker symbol for Netflix. I should use Google to find the ticker symbol.

COMMAND:
GOOGLE: netflix ticker symbol
EXECUTENOW

OUTPUT:
[
    {
        "title": "Netflix, Inc. (NFLX) Stock Price, News, Quote & History - Yahoo Finance",
        "href": "https://finance.yahoo.com/quote/nflx/",
        "body": "Netflix, Inc. (NFLX) NasdaqGS - NasdaqGS Real Time Price. Currency in USD Follow 2W 10W 9M 338.06 -8.13 (-2.35%) As 
of 01:29PM EDT. Market open. 1d 5d 1m 6m YTD 1y 5y Max Full screen Trade..."
    },
    {
        "title": "Netflix Inc (NFLX) Stock Price & News - Google Finance",
        "href": "https://www.google.com/finance/quote/NFLX:NASDAQ",
        "body": "Netflix Inc (NFLX) Stock Price & News - Google Finance Home NFLX • NASDAQ Netflix Inc Follow Share $337.07 Apr 12, 12:56:21 PM GMT-4 · USD · NASDAQ · Disclaimer search Compare to Tesla..."
    },
    {
        "title": "Netflix, Inc. Common Stock (NFLX) Stock Price, Quote, News & History ...",
        "href": "https://www.nasdaq.com/market-activity/stocks/nflx",
        "body": "Netflix is the largest SVOD platform in the world Key Executives Trending Stocks TSLA Tesla, Inc. Common Stock $202.77 -2.94 1.43% AMC AMC Entertainment Holdings, Inc. Class A Common Stock $6.57..."
    },
    {
        "title": "NFLX | Netflix Inc. Stock Price & News - WSJ",
        "href": "https://www.wsj.com/market-data/quotes/NFLX",
        "body": "NFLX | Netflix Inc. Stock Price & News - WSJ Netflix Inc. NFLX (U.S.: Nasdaq) AT CLOSE 4:00 PM EDT 04/12/23 $331.03USD -7.18 -2.12% AFTER HOURS 7:59 PM EDT 04/12/23 $330.25 -0.78 -0.24%..."
    },
    {
        "title": "NFLX Stock Price | Netflix Inc. Stock Quote (U.S.: Nasdaq) - MarketWatch",
        "href": "https://www.marketwatch.com/investing/stock/nflx",
        "body": "Netflix Inc. Watch list Create NFLX Alert Premarket Last Updated: Apr 13, 2023 5:25 a.m. EDT Delayed quote $ 332.50 
1.47 0.44% Before Hours Volume: 2.34K Advanced Charting Volume: 3.97M 65..."
    }
]

RESEARCHER THOUGHTS:
I found the ticker symbol for Netflix. I should run SUCCESS.

COMMAND:
SUCCESS: The ticker symbol for Netflix is NFLX.
EXECUTENOW

=== RESEARCH PROBLEM 2 ===

FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

CURRENT SUBTASK:
{current_subtask}

SUPERVISOR ADVICE:
{supervisor_advice}

>>>>>>>>>>>> START TRIAL 1 <<<<<<<<<<<<

RESEARCHER THOUGHTS:
"""


model = "text-davinci-003"
max_tokens = 4096

def get_current_subtask_categories(subtasks, environment, main_goal, model, current_task, current_task_description):
    current_subtask_category_result = model_interaction.model_call(
        SUBTASK_CATEGORIZER_PROMPT_FORM.format(
            environment=environment, 
            goal=main_goal, 
            current_task=current_task + ": " + current_task_description,
            subtask_list=re.sub("Subtask", "Task", subtasks_to_string(subtasks)),
            subtask_number=1,
            subtask_name=subtasks[0][0],
            subtask_description=subtasks[0][1]
        ),
        model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="subtask categorizer")
    
    print("\nCURRENT SUBTASK:")
    print(subtasks[0][0] + ": " + subtasks[0][1])
    print("\nCURRENT SUBTASK CATEGORY:")
    print(current_subtask_category_result)
    current_subtask_category_matches = re.findall('\((\d*)\)', current_subtask_category_result)
    return current_subtask_category_matches


def subtasks_to_string(subtasks):
    return '\n'.join([f"Subtask {i + 1}. {subtask.strip()}: {subtask_description}" for i, (subtask, subtask_description) in enumerate(subtasks)])

def run(cmd):
    completed = subprocess.run(["powershell", "-Command", cmd], stdout=subprocess.PIPE).stdout.decode('utf-8')
    return completed

def main(environment="Fresh install of Ubuntu; command line access only. Apt and a text editor are already installed.\
Do not research what coding libraries to use; you should be experienced enough to know what you need and how to write the functions you need.\
Try to only use the research tools to look up information that isn't related to coding.", main_goal="Write a 2D raytracing library in C++ for use in 2D platformers, complete with shadows, reflections and refractions.", verbose=True, num_retries=3):

    main_goal = main_goal.strip('.')

    print("Planning High-Level Tasks...")
    planning_agent_prompt = INITIAL_PLANNING_AGENT_PROMPT_FORM.format(environment=environment, goal=main_goal)
    tasks_string = model_interaction.model_call(planning_agent_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="planning agent")
    print("\nTASK LIST:")
    print(tasks_string)

    task_list = re.findall('Task (\d+?)\. (.*?):(.*?)\n', tasks_string)
    
    for task_number, task, task_description in task_list:
                
        print(f"\nPlanning Task {task_number} Subtasks...")
        subtasks_result = model_interaction.model_call(SUBTASKER_PROMPT_FORM.format(environment=environment, goal=main_goal, task_list=tasks_string, task_number=task_number, task_name=task, task_description=task_description),
                                                    model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="subtasker")
        print("\nSUBTASK LIST:")
        print(subtasks_result)

        res = len(re.findall("TASK", subtasks_result))
        if res > 0:
            subtasks_result = subtasks_result.split("\nTASK")[0].strip()

        subtasks = re.findall('Subtask \d*?\.\s*(.*?):(.*?)\n', subtasks_result)

        
        while len(subtasks) > 0:

            current_subtask_category_matches = get_current_subtask_categories(subtasks, environment, main_goal, model, current_task=task, current_task_description=task_description)
        
            if len(current_subtask_category_matches) > 1:
                
                

                print("SPLITTING SUBTASK 1 INTO MULTIPLE SUBTASKS...")
                subtasker_prompt = SUBTASKER_PROMPT_FORM.format(environment=environment, goal=main_goal, task_list=re.sub("Subtask", "Task", subtasks_to_string(subtasks)), task_number=1, task_name=subtasks[0][0], task_description=subtasks[0][1])
                subtasks_to_append = model_interaction.model_call(subtasker_prompt,
                                                        model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="subtasker")
                subtasks_to_append = re.findall('Subtask \d+?\.(.*?):(.*?)(?:\n|$)', subtasks_to_append)
                print("NEW SUBTASKS:")
                print(subtasks_to_string(subtasks_to_append))
                subtasks = subtasks_to_append + subtasks[1:]
                print("NEW SUBTASK LIST:")
                print(subtasks_to_string(subtasks))
                subtasks = subtasks
                new_memory_string = "I split subtask 1 into these subtasks:" + subtasks_to_string(subtasks).replace('\n', ', ')
                all_memory.append(new_memory_string)
                all_pinecone_memory.add(new_memory_string)
                continue

            current_subtask_category = int(current_subtask_category_matches[0].strip(')').strip('(').strip()) if current_subtask_category_matches else None



            category_of_work = "writing code" if current_subtask_category == 1 else "executing terminal commands" \
                if current_subtask_category == 2 else "doing research" \
                if current_subtask_category == 3 else "debugging" \
                if current_subtask_category == 4 else "breaking down the problem"
            type_of_agent = "developer" if current_subtask_category == 1 else "developer" \
                if current_subtask_category == 2 else "researcher" \
                if current_subtask_category == 3 else "developer" \
                if current_subtask_category == 4 else "task planner"


            codebase_signatures_string = "\n".join(["{filename}:\n{functions}}".format(
                filename=filename,
                functions=('\n'.join([f"    - {sig}" for sig in signatures]))) for filename, signatures in all_codebase_signatures.items()])

            if verbose:
                print("\nAll codebase signatures:")
                print(codebase_signatures_string + '\n' if len(all_codebase_signatures) > 0 else "None")

            if len(all_codebase_signatures) > 0:
                relevant_code_prompt = RELEVANT_CODE_PROMPT_FORM.format(
                    goal=main_goal,
                    current_task=task + ": " + task_description,
                    current_subtask=subtasks[0][0] + ": " + subtasks[0][1],
                    codebase_signatures=(codebase_signatures_string))
                relevant_code = model_interaction.model_call(relevant_code_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="relevant code finder")
            else:
                relevant_code = "None"
            
            short_term_memories = all_memory[-5:]
            short_term_memories = '\n'.join([f"- {memory}" for memory in short_term_memories])
            long_term_memories = all_pinecone_memory.get_relevant(subtasks[0][1], 5)
            long_term_memories = '\n'.join([f"- {memory}" for memory in long_term_memories])

            supervisor_advice_prompt = SUPERVISOR_ADVICE_PROMPT_FORM.format(
                environment=environment, 
                goal=main_goal,
                current_task=task + ": " + task_description,
                current_subtask=subtasks[0][0] + ": " + subtasks[0][1],
                recent_actions=short_term_memories,
                long_term_memories=long_term_memories)
            supervisor_advice = model_interaction.model_call(supervisor_advice_prompt, model=model, temperature=0.7, max_tokens=400, stop=['==='], model_name_for_verbose="supervisor/advisor")
            
            new_memory_string = f"I sent this message to my {type_of_agent}: {supervisor_advice}"
            all_memory.append(new_memory_string)
            all_pinecone_memory.add(new_memory_string)
            
            if verbose:
                print("RELEVANT CODE:")
                print(relevant_code)
                print("SUPERVISOR ADVICE:")
                print(supervisor_advice)
            
            if current_subtask_category == 1:
                
                print("WRITING CODE...")

                write_code_prompt = WRITE_CODE_PROMPT_FORM.format(goal=main_goal, current_task=task, relevant_code=relevant_code, supervisor_advice=supervisor_advice, subtask_string=subtasks_to_string(subtasks))
                code_output = model_interaction.model_call(write_code_prompt,
                                                        model=model, temperature=0.7, max_tokens=2048, model_name_for_verbose="code writer")
                py_function_regex = "\ndef (.*?):\s*\n"
                py_class_regex = "\nclass (.*?):\s*\n"
                files_to_write = re.findall("File: (.*?)\n", code_output)
                i = 0
                for file_code in code_output.split('File: '):
                    if file_code.strip() == '':
                        continue
                    file_functions = re.findall(py_function_regex, file_code)
                    file_classes = re.findall(py_class_regex, file_code)
                    file_name = files_to_write[i]
                    
                    with open(file_name, 'w') as f:
                        f.write(file_code.split('Code: \n')[1].strip())
                    all_codebase_signatures[file_name] = file_functions + file_classes
                    new_memory_string = f"I wrote these functions and classes in {file_name}:" + ', '.join(file_functions) + '; ' + ', '.join(file_classes)
                    all_memory.append(new_memory_string)
                    all_pinecone_memory.add(new_memory_string)
                    i += 1
                task_result = True
                
            
            elif current_subtask_category == 2:
                print("EXECUTING TERMINAL COMMANDS...")
                terminal_command_prompt = EXECUTE_COMMANDS_PROMPT_FORM.format(
                    environment=environment,
                    goal=main_goal,
                    current_task=task,
                    current_subtask=subtasks[0][0] + ": " + subtasks[0][1],
                    relevant_code=relevant_code,
                    supervisor_advice=supervisor_advice)
                while True:
                    terminal_prompt_output = model_interaction.model_call(terminal_command_prompt, model=model, temperature=0.7, max_tokens=400,
                                                                    stop=['EXECUTENOW'], model_name_for_verbose="terminal command executor")
                    executor_thoughts = terminal_prompt_output.split('COMMAND:')[0].strip()
                    terminal_command = terminal_prompt_output.split('COMMAND:')[1].strip()
                    if terminal_command.strip() == 'SUCCESS':
                        task_result = True
                        break
                    if terminal_command.strip() == 'FAIL':
                        task_result = False
                        break
                    # command_output = subprocess.run(terminal_command, shell=True, stdout=subprocess.PIPE).stdout.decode('utf-8')
                    # command_output = run(terminal_command)
                    command_output = input("Enter command output: ")
                    thought_memory_string = f""
                    new_memory_string = f"{executor_thoughts}\nI ran this terminal command: {terminal_command} and got this output: \n{command_output}"
                    all_memory.append(new_memory_string)
                    all_pinecone_memory.add(new_memory_string)
                    terminal_command_prompt = terminal_command_prompt + f"THOUGHTS:\n{executor_thoughts}\nCOMMAND:\n{terminal_command}\nEXECUTENOW\n\nCommand output:\n{command_output}\n"
            
            elif current_subtask_category == 3:
                print("DOING RESEARCH...")
                research_prompt = RESEARCH_PROMPT_FORM.format(
                    goal=main_goal,
                    current_task=task,
                    current_subtask=subtasks[0][0] + ": " + subtasks[0][1],
                    supervisor_advice=supervisor_advice)
                while True:
                    research_output = model_interaction.model_call(research_prompt, model=model, temperature=0.7, max_tokens=200, stop=['ENDCOMMAND'], model_name_for_verbose="researcher")
                    researcher_thoughts = research_output.split('COMMAND:')[0].strip()
                    research_command = research_output.split('COMMAND:')[1].strip()
                    if research_output.strip().split(':')[0] == 'SUCCESS':
                        task_result = True
                        break
                    if research_output.strip().split(':')[0] == 'FAIL':
                        task_result = False
                        break
                    research_prompt = research_prompt.strip() + f"\nENDCOMMAND\n\nOUTPUT:\n{research_output}\n\nRESEARCHER THOUGHTS:\n"
                    research_output = model_interaction.model_call(research_prompt, model=model, temperature=0.7, max_tokens=400, stop=['ENDCOMMAND'], model_name_for_verbose="researcher")
            else:

                quit()

            
            if task_result == True:
                subtasks.pop(0)
                continue
            else:
                failure_recovery_prompt = FAILURE_RECOVERY_PROMPT_FORM.format(
                    environment=environment,
                    goal=main_goal,
                    current_task=task,
                    relevant_code=relevant_code,
                    category_of_work=category_of_work,
                    type_of_agent=type_of_agent,
                    agent_actions_and_results=agent_actions_and_results
                )
                print("")
                print("\n================FAILURE RECOVERY=================" +
                        failure_recovery_prompt +
                        "\n=================================================")

if __name__=="__main__":
    main()