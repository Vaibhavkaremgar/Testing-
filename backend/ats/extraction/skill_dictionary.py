from ats.extraction.skill_intelligence import SkillIntelligence


def get_skill_dictionary():
    intelligence = SkillIntelligence()
    return intelligence.get_skill_dictionary()


def get_synonym_dictionary():
    intelligence = SkillIntelligence()
    return intelligence.get_synonym_dictionary()


def get_skill_ontology():
    intelligence = SkillIntelligence()
    return intelligence.get_ontology()
