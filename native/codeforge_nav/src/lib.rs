//! `codeforge_nav` -- a native world-navigation kernel for `CodeForge` (Rust via `PyO3`).
//!
//! `CodeForge`'s world is a directed graph: rooms are nodes, exits are edges. Python builds and owns
//! that world; this crate answers the *spatial* questions fast -- the shortest path between two
//! rooms, and reachability (how much of a million-room world is connected from a point). It is the
//! first organ of the polyglot "assimilation" build: Rust used exactly where memory-safe systems
//! speed helps (bulk graph traversal at world scale), behind a narrow FFI, with a pure-Python
//! fallback (`parts.world.navigation`) kept in lockstep and pinned by a parity test.
//!
//! Design: room labels are interned to dense `u32` indices once at construction; adjacency is a
//! flat `Vec<Vec<u32>>`. The graph is built once from the world's edges and then queried many
//! times, so the FFI cost (marshalling the edge list) is paid a single time, not per query.

use pyo3::exceptions::PyOverflowError;
use pyo3::prelude::*;
use std::collections::{HashMap, VecDeque};

/// A compact directed room-graph with fast pathfinding and reachability.
#[pyclass(module = "codeforge_nav")]
pub struct NavGraph {
    /// room label -> interned index
    ids: HashMap<String, u32>,
    /// interned index -> room label (to render a path back into labels)
    labels: Vec<String>,
    /// interned index -> out-neighbours (directed: an exit is one-way unless the seed pairs it)
    adj: Vec<Vec<u32>>,
}

impl NavGraph {
    fn intern(&mut self, label: &str) -> PyResult<u32> {
        if let Some(&id) = self.ids.get(label) {
            return Ok(id);
        }
        let id = u32::try_from(self.labels.len()).map_err(|_| {
            PyOverflowError::new_err("navigation graph exceeds u32 room-id capacity")
        })?;
        self.ids.insert(label.to_string(), id);
        self.labels.push(label.to_string());
        self.adj.push(Vec::new());
        Ok(id)
    }

    /// Breadth-first shortest path (fewest exits) from `src` to `dst`; interned path, inclusive.
    fn bfs_path(&self, src: u32, dst: u32) -> Option<Vec<u32>> {
        if src == dst {
            return Some(vec![src]);
        }
        let n = self.adj.len();
        let mut prev = vec![u32::MAX; n];
        let mut seen = vec![false; n];
        let mut queue = VecDeque::new();
        seen[src as usize] = true;
        queue.push_back(src);
        while let Some(u) = queue.pop_front() {
            for &v in &self.adj[u as usize] {
                if !seen[v as usize] {
                    seen[v as usize] = true;
                    prev[v as usize] = u;
                    if v == dst {
                        let mut path = vec![dst];
                        let mut cur = dst;
                        while cur != src {
                            cur = prev[cur as usize];
                            path.push(cur);
                        }
                        path.reverse();
                        return Some(path);
                    }
                    queue.push_back(v);
                }
            }
        }
        None
    }

    /// Count of rooms reachable from `src`, inclusive (a directed flood-fill).
    fn flood(&self, src: u32) -> usize {
        let n = self.adj.len();
        let mut seen = vec![false; n];
        let mut queue = VecDeque::new();
        seen[src as usize] = true;
        queue.push_back(src);
        let mut count = 1usize;
        while let Some(u) = queue.pop_front() {
            for &v in &self.adj[u as usize] {
                if !seen[v as usize] {
                    seen[v as usize] = true;
                    count += 1;
                    queue.push_back(v);
                }
            }
        }
        count
    }
}

#[pymethods]
impl NavGraph {
    /// Build a directed graph from `(from_label, to_label)` exit edges. Unknown labels are interned
    /// on the fly, so the caller need not pre-declare nodes.
    #[allow(clippy::needless_pass_by_value)] // PyO3 extracts constructor arguments by value; borrowing changes the Python API.
    #[new]
    fn new(edges: Vec<(String, String)>) -> PyResult<Self> {
        let mut graph = Self {
            ids: HashMap::new(),
            labels: Vec::new(),
            adj: Vec::new(),
        };
        for (from, to) in &edges {
            let a = graph.intern(from)?;
            let b = graph.intern(to)?;
            graph.adj[a as usize].push(b);
        }
        Ok(graph)
    }

    /// Number of distinct rooms in the graph.
    const fn node_count(&self) -> usize {
        self.labels.len()
    }

    /// Shortest path (fewest exits) from `src` to `dst` as a list of room labels, inclusive of both
    /// ends; `None` if either room is unknown or `dst` is unreachable from `src`.
    fn path(&self, src: &str, dst: &str) -> Option<Vec<String>> {
        let source = *self.ids.get(src)?;
        let destination = *self.ids.get(dst)?;
        let hops = self.bfs_path(source, destination)?;
        Some(
            hops.into_iter()
                .map(|i| self.labels[i as usize].clone())
                .collect(),
        )
    }

    /// Number of exits on the shortest path from `src` to `dst`; `None` if unreachable/unknown.
    fn distance(&self, src: &str, dst: &str) -> Option<usize> {
        self.path(src, dst).map(|p| p.len() - 1)
    }

    /// How many rooms are reachable from `src` (inclusive); `None` if `src` is unknown. Compare to
    /// `node_count()` for a fast connectivity audit of a large world.
    fn reachable_count(&self, src: &str) -> Option<usize> {
        let source = *self.ids.get(src)?;
        Some(self.flood(source))
    }
}

/// The Python module `codeforge_nav`.
#[pymodule]
fn codeforge_nav(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<NavGraph>()?;
    m.add(
        "__doc__",
        "CodeForge native navigation kernel (Rust/PyO3): fast room pathfinding + reachability.",
    )?;
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn diamond() -> PyResult<NavGraph> {
        // a -> b -> d, a -> c -> d ; plus a direct a -> d for the shortest path
        NavGraph::new(vec![
            ("a".into(), "b".into()),
            ("b".into(), "d".into()),
            ("a".into(), "c".into()),
            ("c".into(), "d".into()),
            ("a".into(), "d".into()),
        ])
    }

    #[test]
    fn path_is_the_fewest_hops() -> PyResult<()> {
        let g = diamond()?;
        assert_eq!(g.path("a", "d"), Some(vec!["a".into(), "d".into()]));
        assert_eq!(g.distance("a", "d"), Some(1));
        assert_eq!(g.distance("a", "a"), Some(0));
        Ok(())
    }

    #[test]
    fn edges_are_directed() -> PyResult<()> {
        let g = NavGraph::new(vec![("a".into(), "b".into())])?;
        assert_eq!(g.path("a", "b"), Some(vec!["a".into(), "b".into()]));
        assert_eq!(g.path("b", "a"), None); // no reverse edge
        Ok(())
    }

    #[test]
    fn unknown_rooms_are_none() -> PyResult<()> {
        let g = diamond()?;
        assert_eq!(g.path("a", "zzz"), None);
        assert_eq!(g.reachable_count("zzz"), None);
        Ok(())
    }

    #[test]
    fn reachability_counts_the_component() -> PyResult<()> {
        let g = diamond()?;
        assert_eq!(g.node_count(), 4);
        assert_eq!(g.reachable_count("a"), Some(4)); // all of a,b,c,d
        assert_eq!(g.reachable_count("d"), Some(1)); // a sink reaches only itself
        Ok(())
    }
}
