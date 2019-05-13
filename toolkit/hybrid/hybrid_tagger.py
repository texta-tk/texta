from toolkit.tagger.text_tagger import TextTagger

class HybridTagger:

    def __init__(self):
        self.taggers = []
    
    def load(self,tagger_ids):
        for tagger_id in tagger_ids:
            tagger = TextTagger(tagger_id)
            tagger.load()
            print(tagger)
            self.taggers.append(tagger)

    def tag_text(self, text):
        tags = []
        for tagger in self.taggers:
            tagger_response = tagger.tag_text(text)
            if tagger_response[0]:
                tags.append(tagger.description)

        return tags
    
    def tag_doc(self, text):
        pass