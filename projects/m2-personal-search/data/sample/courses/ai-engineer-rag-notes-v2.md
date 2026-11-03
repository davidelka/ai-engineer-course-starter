# RAG notes (AI Engineer course) - v2, after lesson 12

## Lexical search
BM25 ranks chunks by term frequency and inverse document frequency. Parameters: k1 controls term saturation (1.2 is a good default, 1.5 for long documents), b controls length normalization (0.75).
It is great for exact names, numbers and codes, and weak for paraphrases.

## Dense retrieval
Embeddings map text to vectors; cosine similarity finds paraphrases and cross-lingual matches.
multilingual-e5 needs the prefixes "query: " and "passage: ".

## Hybrid
Reciprocal Rank Fusion: score = sum of 1/(k + rank) over the lists, with k = 60.
RRF ignores the raw scores, so BM25 and cosine scores never need to be on the same scale.

## Chunking
Chunks of 200-400 tokens with an overlap of about 10-15%. Keep the title and the section path with each chunk.
