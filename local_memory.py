
import dataclasses
import os
from typing import Any, List, Optional
import numpy as np
import orjson
from utils import model_interaction

SAVE_OPTIONS = orjson.OPT_SERIALIZE_NUMPY | orjson.OPT_SERIALIZE_DATACLASS


def create_default_embeddings(embed_dim):
    return np.zeros((0, embed_dim)).astype(np.float32)

class CacheContent:
    def __init__(self, embed_dim=1536, texts=[], embeddings=None):
        if embeddings is None:
            embeddings = np.zeros((0, embed_dim)).astype(np.float32)
        self.embeddings = embeddings
        self.texts = texts
    
    def __repr__(self):
        return f"CacheContent(texts={self.texts}, embeddings={self.embeddings})"
    
    def to_json(self):
        return {
            "texts": self.texts,
            "embeddings": self.embeddings,
        }

class LocalCache:

    # on load, load our database
    def __init__(self, name, embed_dim=1536) -> None:
        self.filename = f"{name}.json"
        if os.path.exists(self.filename):
            with open(self.filename, 'rb') as f:
                loaded = orjson.loads(f.read())
                self.data = CacheContent(embed_dim=embed_dim, **loaded)
        else:
            self.data = CacheContent()

    def add(self, text: str):
        """
        Add text to our list of texts, add embedding as row to our
            embeddings-matrix

        Args:
            text: str

        Returns: None
        """
        if 'Command Error:' in text:
            return ""
        self.data.texts.append(text)

        embedding = model_interaction.get_ada_embedding(text)

        vector = np.array(embedding).astype(np.float32)
        vector = vector[np.newaxis, :]
        self.data.embeddings = np.concatenate(
            [
                vector,
                self.data.embeddings,
            ],
            axis=0,
        )

        with open(self.filename, 'wb') as f:
            out = orjson.dumps(
                self.data.to_json(),
                option=SAVE_OPTIONS
            )
            f.write(out)
        return text

    def clear(self) -> str:
        """
        Clears the redis server.

        Returns: A message indicating that the memory has been cleared.
        """
        self.data = CacheContent()
        return "Obliviated"

    def get(self, data: str) -> Optional[List[Any]]:
        """
        Gets the data from the memory that is most relevant to the given data.

        Args:
            data: The data to compare to.

        Returns: The most relevant data.
        """
        return self.get_relevant(data, 1)

    def get_relevant(self, text: str, k: int) -> List[Any]:
        """"
        matrix-vector mult to find score-for-each-row-of-matrix
         get indices for top-k winning scores
         return texts for those indices
        Args:
            text: str
            k: int

        Returns: List[str]
        """
        embedding = model_interaction.get_ada_embedding(text)

        scores = np.dot(self.data.embeddings, embedding)

        top_k_indices = np.argsort(scores)[-k:][::-1]

        return [self.data.texts[i] for i in top_k_indices]

    def get_closeness_scores(self, text: str) -> List[float]:
        """
        Returns the closeness scores for each text in the cache.

        Args:
            text: The text to compare to.

        Returns: The closeness scores.
        """
        embedding = model_interaction.get_ada_embedding(text)

        scores = np.dot(self.data.embeddings, embedding)

        return scores.tolist()

    def get_stats(self):
        """
        Returns: The stats of the local cache.
        """
        return len(self.data.texts), self.data.embeddings.shape


def __test_localcache():
    lc = LocalCache("test", embed_dim=1536)
    lc.add("test")
    lc.add("test2")
    lc2 = LocalCache("test")
    assert lc2.data.texts == lc.data.texts
    assert lc2.data.embeddings.shape == lc.data.embeddings.shape

if __name__ == "__main__":
    __test_localcache()