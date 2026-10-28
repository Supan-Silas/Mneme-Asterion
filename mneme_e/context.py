"""Same ranked, whole-evidence, skip-overflow packing as frozen benchmark."""
def pack(evidence, count, budget=4096):
    texts = []
    for item in evidence:
        text = f"[{item['timestamp']}] {item['text']}" if item.get('timestamp') else item['text']
        if count('\n'.join(texts + [text])) <= budget:
            texts.append(text)
    return '\n'.join(texts)
