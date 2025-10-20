"""Clustering utilities for authors, organizations, and topics."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Iterable, List, Sequence

import networkx as nx
import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from .models import NormalizedReference


@dataclass
class ClusterSummary:
    label: str
    members: List[str]
    size: int
    metadata: dict


def build_author_clusters(references: Sequence[NormalizedReference], minimum_size: int = 2) -> List[ClusterSummary]:
    graph = nx.Graph()
    for ref in references:
        author_names = [author.name for author in ref.authors if author.name]
        for name in author_names:
            graph.add_node(name)
        for i, author_a in enumerate(author_names):
            for author_b in author_names[i + 1 :]:
                if graph.has_edge(author_a, author_b):
                    graph[author_a][author_b]["weight"] += 1
                else:
                    graph.add_edge(author_a, author_b, weight=1)

    if graph.number_of_nodes() == 0:
        return []

    communities = nx.algorithms.community.greedy_modularity_communities(graph, weight="weight")
    clusters: List[ClusterSummary] = []
    for idx, community in enumerate(communities, start=1):
        members = sorted(list(community))
        if len(members) < minimum_size:
            continue
        clusters.append(
            ClusterSummary(
                label=f"Author Cluster {idx}",
                members=members,
                size=len(members),
                metadata={},
            )
        )
    return clusters


def build_org_clusters(references: Sequence[NormalizedReference], minimum_size: int = 2) -> List[ClusterSummary]:
    graph = nx.Graph()
    for ref in references:
        org_names = [aff.name for aff in ref.affiliations if aff.name]
        org_types = {aff.name: aff.type for aff in ref.affiliations if aff.name and aff.type}
        for org in org_names:
            graph.add_node(org, type=org_types.get(org))
        for i, org_a in enumerate(org_names):
            for org_b in org_names[i + 1 :]:
                if graph.has_edge(org_a, org_b):
                    graph[org_a][org_b]["weight"] += 1
                else:
                    graph.add_edge(org_a, org_b, weight=1)

    if graph.number_of_nodes() == 0:
        return []

    communities = nx.algorithms.community.greedy_modularity_communities(graph, weight="weight")
    clusters: List[ClusterSummary] = []
    for idx, community in enumerate(communities, start=1):
        members = sorted(list(community))
        if len(members) < minimum_size:
            continue
        types = Counter(graph.nodes[member].get("type") for member in members if graph.nodes[member].get("type"))
        clusters.append(
            ClusterSummary(
                label=f"Organisation Cluster {idx}",
                members=members,
                size=len(members),
                metadata={"types": dict(types)},
            )
        )
    return clusters


def build_topic_clusters(references: Sequence[NormalizedReference], desired_k: int = 8) -> List[ClusterSummary]:
    corpus = []
    reference_indices = []
    for idx, ref in enumerate(references):
        text_fragments = [ref.title or "", ref.abstract or ""]
        combined = " ".join(fragment for fragment in text_fragments if fragment)
        if not combined.strip():
            continue
        corpus.append(combined)
        reference_indices.append(idx)

    if len(corpus) < 2:
        return []

    k = min(desired_k, len(corpus))
    vectorizer = TfidfVectorizer(max_features=5000, stop_words="english")
    tfidf_matrix = vectorizer.fit_transform(corpus)
    if k <= 1:
        labels = np.zeros(len(corpus), dtype=int)
    else:
        model = KMeans(n_clusters=k, random_state=42, n_init="auto")
        labels = model.fit_predict(tfidf_matrix)

    feature_names = vectorizer.get_feature_names_out()
    clusters: List[ClusterSummary] = []
    for cluster_id in range(k):
        indices = np.where(labels == cluster_id)[0]
        if len(indices) == 0:
            continue
        cluster_docs = tfidf_matrix[indices]
        centroid = cluster_docs.mean(axis=0)
        centroid = np.asarray(centroid).ravel()
        top_indices = centroid.argsort()[-10:][::-1]
        keywords = [feature_names[i] for i in top_indices if centroid[i] > 0]
        members = [references[reference_indices[i]].title or references[reference_indices[i]].raw for i in indices]
        clusters.append(
            ClusterSummary(
                label=f"Topic Cluster {cluster_id + 1}",
                members=members,
                size=len(members),
                metadata={"keywords": keywords},
            )
        )
    return clusters


def top_entities(values: Iterable[str], top_n: int = 10) -> List[tuple[str, int]]:
    counter = Counter(value for value in values if value)
    return counter.most_common(top_n)

