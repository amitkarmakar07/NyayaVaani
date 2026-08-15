from crewai import Agent, Task, Crew, Process
from crewai.project import CrewBase, agent, task, crew
from src.nyayavaani_crew.tools import state_helpline_tool, department_lookup_tool, legal_rag_tool, twitter_handle_lookup_tool
from src.nyayavaani_crew.schemas import AnalyzerOutput, RouterOutput, WriterOutput, SocialMediaOutput
from crewai import LLM
from config import Config
from src.telemetry import setup_telemetry
import os

os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"
setup_telemetry()

def get_llm():
    model = Config.LLM_MODEL
    if "groq" in model.lower() or "llama" in model.lower():
        api_key = Config.GROQ_API_KEY
        if not model.startswith("groq/"):
            model = f"groq/{model}"
    else:
        api_key = Config.GOOGLE_API_KEY
        if not model.startswith("gemini/"):
            model = f"gemini/{model}"

    return LLM(
        model=model,
        api_key=api_key,
        temperature=0.3
    )

@CrewBase
class NyayaVaaniCrew:
    """NyayaVaani Multi-Agent Civic Grievance Crew"""

    agents_config = 'config/agents.yaml'
    tasks_config = 'config/tasks.yaml'

    # --- AGENTS ---

    @agent
    def analyzer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['analyzer_agent'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def router_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['router_agent'],
            tools=[state_helpline_tool, department_lookup_tool],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def researcher_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher_agent'],
            tools=[legal_rag_tool],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def writer_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['writer_agent'],
            llm=get_llm(),
            verbose=True
        )

    @agent
    def social_media_agent(self) -> Agent:
        return Agent(
            config=self.agents_config['social_media_agent'],
            tools=[twitter_handle_lookup_tool],
            llm=get_llm(),
            verbose=True
        )


    # --- TASKS ---

    @task
    def analyzer_task(self) -> Task:
        return Task(
            config=self.tasks_config['analyzer_task'],
            agent=self.analyzer_agent(),
            output_pydantic=AnalyzerOutput
        )

    @task
    def router_task(self) -> Task:
        return Task(
            config=self.tasks_config['router_task'],
            agent=self.router_agent(),
            context=[self.analyzer_task()],
            output_pydantic=RouterOutput
        )

    @task
    def researcher_task(self) -> Task:
        return Task(
            config=self.tasks_config['researcher_task'],
            agent=self.researcher_agent(),
            context=[self.analyzer_task()]
        )

    @task
    def writer_task(self) -> Task:
        return Task(
            config=self.tasks_config['writer_task'],
            agent=self.writer_agent(),
            context=[self.analyzer_task(), self.router_task(), self.researcher_task()],
            output_pydantic=WriterOutput
        )

    @task
    def social_media_task(self) -> Task:
        return Task(
            config=self.tasks_config['social_media_task'],
            agent=self.social_media_agent(),
            context=[self.analyzer_task(), self.router_task()],
            output_pydantic=SocialMediaOutput
        )

    # --- CREW ---

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            max_rpm=8,
            verbose=True
        )
