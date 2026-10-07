from examples.crewai.ops_email import AGENT_NAME as CREW_NAME
from examples.crewai.ops_email import plan_email as crew_plan
from examples.langchain.ops_email import AGENT_NAME as LANG_NAME
from examples.langchain.ops_email import plan_email as lang_plan
from groundwire.handoff import canned_outage_email


def test_offline_langchain_plan_matches_handoff():
    payload = lang_plan("dns flap", live=False)
    assert payload == canned_outage_email("dns flap")
    assert LANG_NAME == "langchain-ops-email"


def test_offline_crewai_plan_matches_handoff():
    payload = crew_plan("dns flap", live=False)
    assert payload == canned_outage_email("dns flap")
    assert CREW_NAME == "crewai-ops-email"
