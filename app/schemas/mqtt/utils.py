def get_topic_split(topic: str) -> tuple[str, ...]:
    return tuple(topic.split('/'))
