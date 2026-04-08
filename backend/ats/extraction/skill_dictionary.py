from ats.extraction.skill_intelligence import get_skill_engine


def get_skill_dictionary():
    return get_skill_engine().get_skill_dictionary()


def get_synonym_dictionary():
    return get_skill_engine().get_synonym_dictionary()


def get_skill_ontology():
    return get_skill_engine().get_ontology()
