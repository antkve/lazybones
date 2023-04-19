
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

RELEVANT LONG-TERM MEMORIES:
{long_term_memories}

RECENT ACTIONS:
{recent_actions}

SUBTASK LIST FORMAT:
- <Subtask description>
- <Subtask description>
...

TASK {task_number} SUBTASKS:
"""

SUPERVISOR_CODE_QUESTION_PROMPT_FORM = """
You are reading your code, trying to answer the following question:
{question}

ENVIRONMENT:
{environment}

FINAL GOAL:
{goal}

CODE SECTIONS:
{code_chunk}

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
GOAL:
{goal}

TASK LIST:
{task_list}

My employee has asked me the following question:
{question}

After I gave him the following goal and instructions:
"{subtask}: {supervisor_advice}"

Here is what I remember:
{memory_summary}

Here is what I know about each part of my code:
{code_summary}

Here is my answer:
"""

SUBTASK_UPDATER_PROMPT_FORM = """
ENVIRONMENT:
{environment}

GOAL:
{goal}

CURRENT TASK LIST:
{task_list}

RECENT THOUGHTS AND ACTIONS:
{command_strings}

SUPERVISOR MESSAGE:
{supervisor_advice}

Based on the agent's recent actions and their supervisor's advice, update their list of subtasks. Make sure to only include subtasks that are part of the current task.

CURRENT SUBTASK LIST:
{subtask_list}

UPDATED SUBTASK LIST:
"""
SUPERVISOR_ADVICE_PROMPT_FORM = """
Based on the developer's recent actions, give them advice on their current task.
Include any the information you think would help them.
If the developer has done something wrong, let them know.
Make sure they stick to their current task, or tell them to mark it as complete if they have finished it.

ENVIRONMENT:
{environment}

=== PROBLEM 1 ===

=== TRIAL 1 ===

FINAL GOAL:
Create a binary calculator program in python.

CURRENT TASK:
Write arithmetic functions: Write some python functions for doing arithmetic on binary strings.

CURRENT SUBTASKS:
- Write test for BinaryString class
- Write test for add_two_numbers
- Write test for subtract_two_numbers
- Write test for multiply_two_numbers
- Run the tests

DEVELOPER'S RELEVANT LONG-TERM MEMORIES:
- I wrote the following functions/classes in binary_arithmetic.py: BinaryString(str) add_two_numbers(a, b), subtract_two_numbers(a, b), multiply_two_numbers(a, b)
- I ran the following command: pip install unittest
- I installed python and unittest

RECENT DEVELOPER ACTIONS:
- I wrote some comments in main.py
- I wrote the following functions/classes in test_binary_arithmetic.py: test_binary_string(a), test_add_two_numbers(a, b)
- I wrote the following functions/classes in logging.py: log(message), log_error(message), log_warning(message), log_success(message)
- I ran the command 'python main.py' and got the following output: "Hello world!"
- I ran the command 'pip install dotenv' and got the following output: "Successfully installed dotenv-0.19.0"

MESSAGE:
Now you should write a test for the binary add_two_numbers function, which you've written in binary_arithmetic.py. The test should include at least 5 test cases,
and should be in a file called test_binary_arithmetic.py. It should use the unittest module.

=== TRIAL SUCCESS ===

=== PROBLEM 2 ===

=== TRIAL 1 ===

FINAL GOAL:
{goal}

CURRENT TASK:
{current_task}

CURRENT SUBTASKS:
{current_subtasks}

DEVELOPER'S RELEVANT LONG-TERM MEMORIES:
{long_term_memories}

RECENT DEVELOPER ACTIONS:
{recent_actions}

MESSAGE:
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

WRITE_FILE:
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
<what to modify and all
relevant information>
>ENDACTION
OUTPUT:
<resulting code>

MARK_TASK_COMPLETE:
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

SUPERVISOR INSTRUCTIONS:
{supervisor_advice}

ACTION EXECUTION SYNTAX:
\"\"\"
>THOUGHTS:
thoughts about the last output and reasoning behind your current action
>ACTION:
ACTION_NAME:
arg1
[arg2]
>ENDACTION
\"\"\"

After each action, wait for the output. After each output, give your next thoughts and action.
Ask the Supervisor any questions you have about the codebase or what has been done in the project so far.
You should complete your subtasks in the order they are given, and make sure to run MARK_TASK_COMPLETE before you move onto the next task.

=== CONTINUING TRIAL 1 ===

>THOUGHTS:"""

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