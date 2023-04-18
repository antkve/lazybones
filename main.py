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
- <Subtask name>: <Subtask description>

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
>GOOGLE:
<search term>
>ENDACTION
OUTPUT:
{<search result 1>, <search result 2>, ...}

>BROWSE:
<url>
<question to try and answer when browsing>
>ENDACTION
OUTPUT:
<answer>

>RUN_TERMINAL_COMMAND:
<command>
>ENDACTION
OUTPUT:
<terminal output>

>DO_NOTHING:
<reason for waiting>
>ENDACTION
OUTPUT:
None

>NEW_FILE:
<filename>
<file contents>
>ENDACTION
OUTPUT:
<success/failure>

>READ_FILE:
<filename>
>ENDACTION
OUTPUT:
<file contents>

>ADD_TO_FILE:
<filename>
<content
to
add>
>ENDACTION
OUTPUT:
<success/failure>

>DELETE_FILE:
<filename>
>ENDACTION
OUTPUT:
<success/failure>

>MODIFY_CODE:
<filename>
<text describing precisely
which lines to modify
and how>
>ENDACTION
OUTPUT:
<success/failure>

>MARK_SUBTASK_COMPLETE:
<success/failure>
>ENDACTION
OUTPUT:
None

>ASK_SUPERVISOR:
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
model = "text-davinci-003"
max_tokens = 4096

def subtasks_to_string(subtasks):
    return '\n'.join([f"- {subtask.strip()}: {subtask_description}" for i, (subtask, subtask_description) in enumerate(subtasks)])

def tasks_to_string(tasks, current_subtask_number=None):
    task_strings = [f"Task {i + 1}. {task.strip()}: {task_description}" for i, (task, task_description) in enumerate(tasks)]
    if current_subtask_number is not None:
        task_strings[current_subtask_number] += " (Current task)"
    return '\n'.join()

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

        subtasks = re.findall('- (.*?):(.*?)\n', subtasks_result)
        

        while len(subtasks) > 0:
            
            base_executor_prompt = EXECUTOR_PROMPT_FORM.format(
                environment=environment,
                available_actions=ACTIONS,
                goal=main_goal,
                current_tasks=tasks_to_string(task_list, task_number),
                current_subtasks=subtasks_to_string(subtasks),
                supervisor_advice=supervisor_advice
            )
            base_executor_prompt = base_executor_prompt + '\n'.join(command_strings)
            # Command string format:
            # <thoughts>
            # ...
            # >THOUGHTS:
            executor_output = model_interaction.model_call(executor_prompt, model=model, temperature=0.7, max_tokens=max_tokens, stop=["ENDCOMMAND"] model_name_for_verbose="executor")
            executor_thoughts = re.findall("^(.*?)>", executor_output, re.DOTALL)[0].strip()
            executor_action = re.findall(">ACTION:\n>(.*?)\nENDACTION", executor_output, re.DOTALL)[0].strip()
            executor_action_name = executor_action.split(":")[0]
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
                res = "Finished subtask {subtask}".format(subtask=subtasks[0][0] + ": " + subtasks[0][1])
                memory = "I finished the subtask {subtask}".format(subtask=subtasks[0][0] + ": " + subtasks[0][1])
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

            supervisor_advice_prompt = SUPERVISOR_QUESTION_PROMPT_FORM.format(
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