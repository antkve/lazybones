import os
import unittest

import dotenv
dotenv.load_dotenv()
import re
from utils import model_interaction
import subprocess
from local import LocalCache
import tools.browsing


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
- <Subtask description>

TASK {task_number} SUBTASKS:
"""

SUPERVISOR_CODE_QUESTION_PROMPT_FORM = """
You are reading your code, trying to answer the following question:
{question}

ENVIRONMENT:
{environment}

FINAL GOAL:
{goal}

RELEVANT CODE:
{relevant_code}

Summarize all the information about this code that might help to answer the question.
If there is no code relevant to this question here, write "None".
If there is anything missing that would be helpful for you to know before answering the question, mention it.

Summary:
"""

SUPERVISOR_MEMORY_QUESTION_PROMPT_FORM = """
You are searching through your memories, trying to answer to this question:
{question}

ENVIRONMENT:
{environment}

FINAL GOAL:
{goal}

MEMORIES:
{memory_chunk}

Summarize all the information about these memories that might help to answer your question.
If there are no memories relevant to this question, write "None".
If there is anything missing that would be helpful for you to know before answering the question, mention it.

Summary:
"""

SUPERVISOR_QUESTION_PROMPT_FORM = """
Give the answer to the following question:
{question}

Here is what I remember:
{memory_summary}

Here is what I know about each part of my code:
{code_summary}

Answer:
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

RECENT ACTIONS AND THOUGHTS:
{recent_actions}

RELEVANT LONG-TERM MEMORIES:
{long_term_memories}

MESSAGE:
"""
MEMORY_RELEVANCE_PROMPT_FORM = """
The memory relevance scores should answer the following question:
"If this task has failed, how helpful would this memory be in figuring out what went wrong?".
Give your answers out of 10.

=== TRIAL 1 ===

FINAL GOAL:
Create a binary calculator program in python.

TASKS:
Task 1. Write arithmetic functions: Write some python functions for doing arithmetic on binary strings.
Task 2. Write tests: Write some tests for the arithmetic functions.
Task 3. Run tests: Run the tests for the arithmetic functions. (Current task)
Task 4. Write main.py: Write the main.py file, which will be the entry point for the program.
Task 5. Run main.py: Run the main.py file, and make sure it works.

MEMORY:
I wrote the test_add_two_numbers function in test_utils.py, which tests the add_two_numbers function in utils.py.

MEMORY RELEVANCE SCORES:
Task 1:
Reasoning: If the add_two_numbers function is broken, then the test_add_two_numbers function will fail, and this will help me figure out what went wrong, so this memory is highly relevant to task 1. 
Score: 8
Task 2:
Reasoning: test_add_two_numbers is one of the tests involved in this task, so it is highly relevant.
Score: 10
Task 3:
Reasoning: test_add_two_numbers is one of the tests involved in this task, so it is highly relevant.
Score: 9
Task 4:
Reasoning: If I fail to write this file, then this memory will not be helpful in figuring out what went wrong, so it is not very relevant.
Score: 3
Task 5:
Reasoning: If running main.py fails, then this memory may help me rule out the add_two_numbers_function as the cause of the failure, so it is moderately relevant.
Score: 5

=== TRIAL 2 ===

FINAL GOAL:
{goal}

TASKS:
{tasks}

MEMORY:
{memory}

MEMORY RELEVANCE SCORES:
"""

ACTIONS = """
GOOGLE:
<search term>
>ENDACTION
OUTPUT:
{<search result 1>, <search result 2>, ...}

BROWSE:
<url>
<question to try and answer when browsing>
>ENDACTION
OUTPUT:
<answer>

RUN_TERMINAL_COMMAND:
<command>
>ENDACTION
OUTPUT:
<terminal output>

DO_NOTHING:
<reason for waiting>
>ENDACTION
OUTPUT:
None

NEW_FILE:
<filename>
<file contents>
>ENDACTION
OUTPUT:
<success/failure>

READ_FILE:
<filename>
>ENDACTION
OUTPUT:
<file contents>

ADD_TO_FILE:
<filename>
<content
to
add>
>ENDACTION
OUTPUT:
<success/failure>

DELETE_FILE:
<filename>
>ENDACTION
OUTPUT:
<success/failure>

MODIFY_CODE:
<filename>
<text describing precisely
which lines to modify
and how>
>ENDACTION
OUTPUT:
<success/failure>

MARK_SUBTASK_COMPLETE:
<success/failure>
>ENDACTION
OUTPUT:
None

ASK_SUPERVISOR:
<question to ask omniscient supervisor>
>ENDACTION
OUTPUT:
<supervisor answer>
"""


EXECUTOR_PROMPT_FORM = """
=== INFO ===

ENVIRONMENT:
{environment}

AVAILABLE ACTIONS:
{actions}

FINAL GOAL:
{goal}

COMPLETE TASK LIST:
{current_tasks}

CURRENT SUBTASK LIST:
{current_subtasks}

SUPERVISOR ADVICE:
{supervisor_advice}

ACTION EXECUTION SYNTAX:
\"\"\"
>THOUGHTS:
thoughts about the last output and reasoning behind the current action
>ACTION:
>ACTION_NAME:
arg1
...
>ENDACTION
\"\"\"

After each output, give your next thoughts and action.
Ask the Supervisor any questions you have about the codebase or what has been done in the project so far.

=== CONTINUING TRIAL 1 ===

>THOUGHTS:
"""

MEMORY_SUMMARY_PROMPT_FORM = """
FINAL GOAL:
{goal}

COMPLETE TASK LIST:
{current_tasks}

CURRENT SUBTASK LIST:
{current_subtasks}

PAST ACTIONS:
{memory_chunk}

Write 1-2 paragraphs explaining what you did, what you learned and what you struggled with,
in a way which would be helpful when trying to answer the following question:
{question}

ANSWER:"""
class TaskComplete(Exception):
    pass
model = "gpt-3.5-turbo" #"text-davinci-003"
max_tokens = 4096

def subtasks_to_string(subtasks):
    return '\n'.join([f"- {subtask.strip()}: {subtask_description}" for i, (subtask, subtask_description) in enumerate(subtasks)])

def tasks_to_string(tasks, current_subtask_number=None):
    task_strings = [f"Task {i + 1}. {task.strip()}: {task_description}" for i, (task, task_description) in enumerate(tasks)]
    if current_subtask_number is not None:
        task_strings[current_subtask_number] += " (Current task)"
    return '\n'.join(task_strings)

def run(cmd):
    completed = subprocess.run(["powershell", "-Command", cmd], stdout=subprocess.PIPE).stdout.decode('utf-8')
    return completed

def main(environment="Fresh install of Ubuntu; command line access only. Apt and a text editor are already installed. Do not research unless you have to.", main_goal="Write a 2D raytracing library in C++ for use in 2D platformers, complete with shadows, reflections and refractions.", verbose=True, num_retries=3):

    codebase_memory = LocalCache("CodebaseMemory")
    codebase_signatures = {} # {filename: [signature1, signature2, ...], ...}

    main_goal = main_goal.strip('.')

    print("Planning High-Level Tasks...")
    planning_agent_prompt = INITIAL_PLANNING_AGENT_PROMPT_FORM.format(environment=environment, goal=main_goal)
    planning_agent_output = model_interaction.model_call(planning_agent_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="planning agent")

    task_list = re.findall('Task \d+?\. (.*?):(.*?)\n', planning_agent_output)
    command_strings = []
    actions_memory = LocalCache("actions_memory")

    for task_number, (task, task_description) in enumerate(task_list):
        
        print(f"\nPlanning Task {task_number} Subtasks...")
        subtasks_result = model_interaction.model_call(
            SUBTASKER_PROMPT_FORM.format(
                environment=environment,
                goal=main_goal, 
                task_list=tasks_to_string(task_list), 
                task_number=task_number, 
                task_name=task, 
                task_description=task_description
            ),
            model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="subtasker"
        )

        res = len(re.findall("TASK", subtasks_result))
        if res > 0:
            subtasks_result = subtasks_result.split("\nTASK")[0].strip()

        subtasks = re.findall('(?:\n|^)- (.*?):(.*?)\n', subtasks_result)
        
        while len(subtasks) > 0:
            long_term_memories = actions_memory.get_relevant('\n'.join(command_strings[-5:]), 5) if len(command_strings) > 0 else []
            supervisor_advice_prompt = SUPERVISOR_ADVICE_PROMPT_FORM.format(
                environment=environment,
                goal=main_goal, 
                current_task=f"{task}: {task_description}",
                current_subtask=f"{subtasks[0][0]}: {subtasks[0][1]}",
                recent_actions='\n'.join(command_strings[-5:]),
                long_term_memories='\n'.join(long_term_memories)
            )
            supervisor_advice_output = model_interaction.model_call(supervisor_advice_prompt, model=model, temperature=0.7, max_tokens=400, model_name_for_verbose="supervisor")
            base_executor_prompt = EXECUTOR_PROMPT_FORM.format(
                environment=environment,
                actions=ACTIONS,
                goal=main_goal,
                current_tasks=tasks_to_string(task_list, task_number),
                current_subtasks=subtasks_to_string(subtasks),
                supervisor_advice=supervisor_advice_output
            )
            executor_prompt = base_executor_prompt + '\n'.join(command_strings)
            # Command string format:
            # <thoughts>
            # ...
            # >THOUGHTS:
            executor_output = model_interaction.model_call(executor_prompt, model=model, temperature=0.7, max_tokens=1000, stop=[">ENDACTION"], model_name_for_verbose="executor")
            executor_thoughts = re.findall("^(.*?)>", executor_output, re.DOTALL)[0].strip()
            executor_action = re.findall(">ACTION:\n(.*?)\n", executor_output)[0].strip()
            executor_action_name = executor_action.split(":")[0].strip()
            executor_action_arg_1 = executor_action.split('\n')[1].strip()
            executor_action_arg_2 = '\n'.join(executor_action.split('\n')[2:]).strip() if len(executor_action.split('\n')) > 2 else None


            if executor_action_name == "GOOGLE":
                res = tools.browsing.google_search(executor_action_arg_1)
                memory = f"I googled '{executor_action_arg_1}' and found {res}"
            elif executor_action_name == "BROWSE":
                res = tools.browsing.browse_website(executor_action_arg_1, executor_action_arg_2)
                memory = f"I browsed to {executor_action_arg_1} to answer the question \"{executor_action_arg_2}\" and got the following result: {res}"
            elif executor_action_name == "RUN_TERMINAL_COMMAND":
                res = run(executor_action_arg_1)
                memory = f"I ran the command '{executor_action_arg_1}' and got the following result: {res}"
            elif executor_action_name == "DO_NOTHING":
                res = "None"
                memory = "I did nothing."
            elif executor_action_name == "NEW_FILE":
                res = tools.file_operations.write_to_file(executor_action_arg_1, executor_action_arg_2)
                memory = f"I created a new file called '{executor_action_arg_1}' and wrote the following to it:\n{executor_action_arg_2}"
            elif executor_action_name == "READ_FILE":
                res = tools.file_operations.read_file(executor_action_arg_1)
                memory = f"I read the file '{executor_action_arg_1}'"
            elif executor_action_name == "ADD_TO_FILE":
                res = tools.file_operations.write_to_file(executor_action_arg_1, executor_action_arg_2)
                new_functions = ', '.join(re.findall("def (.*?):\n", executor_action_arg_2, re.DOTALL))
                new_classes = ', '.join(re.findall("(class .*?):\n", executor_action_arg_2, re.DOTALL))
                memory = f"I added these new functions and classes to '{executor_action_arg_1}':\n{new_functions}; {new_classes}"
            elif executor_action_name == "DELETE_FILE":
                res = tools.file_operations.delete_file(executor_action_arg_1)
                memory = f"I deleted the file '{executor_action_arg_1}'"
            elif executor_action_name == "MODIFY_CODE":
                code_text = tools.file_operations.read_file(executor_action_arg_1)
                res = model_interaction.edit_call(code_text, executor_action_arg_2, model=model, temperature=0.7, max_tokens=2000, model_name_for_verbose="code editor")
                tools.file_operations.write_to_file(executor_action_arg_1, res)
                memory = f"I modified the file '{executor_action_arg_1}' based on the following instructions:\n{executor_action_arg_2}"

            elif executor_action == "MARK_SUBTASK_COMPLETE":
                subtasks = subtasks[1:]
                res = "Finished subtask '{subtask}'".format(subtask=subtasks[0][0] + ": " + subtasks[0][1])
                memory = "I marked the subtask '{subtask}' as completed".format(subtask=subtasks[0][0] + ": " + subtasks[0][1])
            elif executor_action == "ASK_SUPERVISOR":

                supervisor_memory_question_prompt = SUPERVISOR_MEMORY_QUESTION_PROMPT_FORM.format(
                    question=executor_action_arg_1,
                    environment=environment,
                    goal=main_goal,
                    memory_chunk='\n -'.join(actions_memory.data.texts)
                )
                supervisor_code_question_prompt = SUPERVISOR_CODE_QUESTION_PROMPT_FORM.format(
                    question=executor_action_arg_1,
                    environment=environment,
                    goal=main_goal,
                    code_chunk='\n -'.join(codebase_signatures_string)
                )
                supervisor_advice_prompt = SUPERVISOR_QUESTION_PROMPT_FORM.format(
                    environment=environment, 
                    goal=main_goal,
                    current_task=task + ": " + task_description,
                    current_subtask=subtasks[0][0] + ": " + subtasks[0][1],
                    recent_actions=short_term_memories,
                    long_term_memories=long_term_memories)
                supervisor_advice = model_interaction.model_call(supervisor_advice_prompt, model=model, temperature=0.7, max_tokens=400, stop=['==='], model_name_for_verbose="supervisor/advisor")
                
            actions_memory.add(memory)
            command_string = f"{command_string}\n>ENDACTION\nOUTPUT:\n{res}\n"
            command_strings.append(command_string)

if __name__=="__main__":
    main()