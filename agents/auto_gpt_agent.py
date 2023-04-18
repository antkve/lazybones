from .. import tools
import json

from agent import ContinuousAgent

class AutoGPT(ContinuousAgent):
    """
    Continuous agent with persistent memory (both short- and long-term), a static introductory prompt and a set of tools to use.
    """
    def __init__(self, name, goal, description="a problem-solving AI agent", agent_tools={}, system_advice=[],
                 temperature=0.7, model="gpt-3.5-turbo"):
        super().__init__(name, model, temperature)

        self.agent_tools = agent_tools

        self.all_tools = {**tools.BASE_TOOLS, **self.agent_tools}
        self.last_task_result = "Task has begun. Trial 1 started."
        system_advice = '\n'.join([f"{i + 5}. {advice.strip('.')}." for i, advice in enumerate(system_advice)])
        
        self.intro_prompt = f"""
        You are {name}, {description.strip().strip(".")}.

        CONSTRAINTS:

        1. ~2000 word limit for short term memory. Your short term memory is short, so immediately save important information to files.
        2. Exclusively use the commands listed in double quotes e.g. "command_name"
        3. Responses must be parsable JSON.
        4. What appears in your long term memory depends on what you think about.

        GOAL:

        {goal}

        COMMANDS:

        {tools.tool_list_to_string(self.all_tools)}

        PERFORMANCE EVALUATION:
        1. Continuously review and analyze your actions to ensure you are performing to the best of your abilities. 
        2. Constructively self-criticize your big-picture behavior constantly.
        3. Reflect on past decisions and strategies to refine your approach.
        4. Every command has a cost, so be smart and efficient. Aim to complete tasks in the least number of steps.
        {system_advice}""" + """

        You can only respond in JSON format as described below

        RESPONSE FORMAT:
        {
            "thoughts":
            {
                "text": "thought",
                "reasoning": "reasoning",
                "plan": "- short bulleted\n- list that conveys\n- short-term plan",
                "criticism": "constructive self-criticism",
                "speak": "summary of thoughts to say to user"
            },
            "command": {
                "name": "command_name",
                "args":{
                    "arg name": "value"
                }
            }
        }

        Ensure each of your responses can be parsed by Python json.loads.
        """
        
    
    def get_agent_step(self):
        prompt = self.__get_current_state()
        agent_response = self.prompt(prompt)
        response_json = json.loads(agent_response)
        result = self.all_tools[response_json["command"]["name"]](**response_json["command"]["args"])
        event_string = f"""
        Agent Thoughts: {response_json["thoughts"]}
        Agent Command: {response_json["command"]}
        Command Result: {result}
        """
        self.__add_event_to_short_term_memory(event_string)
    