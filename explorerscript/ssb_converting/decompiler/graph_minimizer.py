#  MIT License
#
#  Copyright (c) 2020 Parakoopa
#
#  Permission is hereby granted, free of charge, to any person obtaining a copy
#  of this software and associated documentation files (the "Software"), to deal
#  in the Software without restriction, including without limitation the rights
#  to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
#  copies of the Software, and to permit persons to whom the Software is
#  furnished to do so, subject to the following conditions:
#
#  The above copyright notice and this permission notice shall be included in all
#  copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
#  IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
#  FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
#  AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
#  LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
#  OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
#  SOFTWARE.
#
import sys
import warnings
from enum import Enum, auto
from typing import List, Union, Set, Dict, Tuple

from igraph import Graph, IN, OUT

from explorerscript.ssb_converting.decompiler.graph_utils import *
from explorerscript.ssb_converting.ssb_data_types import SsbOperation
from explorerscript.ssb_converting.ssb_special_ops import SsbLabelJump, OPS_THAT_END_CONTROL_FLOW, SsbLabel, OP_HOLD, \
    OP_JUMP, OPS_BRANCH, SsbIfStart, SsbIfEnd


class ControlFlowToken(Enum):
    # Building the control flow was aborted, because after reaching the node before this token the flow loops
    LOOP = auto()


ControlFlowItem = Union[SsbOperation, ControlFlowToken]
sys.setrecursionlimit(10000)


class SsbGraphMinimizer:
    def __init__(self, routine_ops: List[List[SsbOperation]]):
        self._graphs: List[Graph] = []
        for rtn_id, rtn in enumerate(routine_ops):
            g = Graph(directed=True)
            self._graphs.append(g)
            if len(rtn) < 1:
                # Should not happen
                continue
            # Map of label id -> id of opcode in routine
            label_indices: Dict[int, int] = {}
            for i, op in enumerate(rtn):
                v = g.add_vertex(i, label=None, op=op, style='solid', shape='ellipse')
                if isinstance(op, SsbLabel):
                    label_indices[op.id] = i
                self._update_vertex_style(v)
            self._get_edges(g, rtn, rtn_id, label_indices)

    def count_labels(self):
        # TODO
        return 0

    def get_control_flow(self) -> List[List[List[ControlFlowItem]]]:  # for each routine: for each run: list of cfi
        """
        Traverses the current graphs for each routine and returns possible control flows.
        Returns all possible control flows through a routine.

        Return is a list of op_codes and some special tokens (see enum ControlFlowToken).
        """
        # TODO
        return None

    def optimize_paths(self):
        """Perform some general optimizations."""
        for g in self._graphs:
            vs_to_delete = []
            for v in g.vs:
                if isinstance(v['op'], SsbLabelJump) and v['op'].root.op_code.name == OP_JUMP:
                    # IS JUMP.
                    ins = g.incident(v, IN)
                    if len(ins) == 1:
                        iv = g.es[ins[0]].source_vertex
                        if isinstance(iv['op'], SsbLabel):
                            # IS JUMP AND BEFORE IS LABEL:
                            vs_to_delete += self._optimize_paths__jump_after_label(g, jump=v, label=iv)
            g.delete_vertices(vs_to_delete)

    def _optimize_paths__jump_after_label(self, g, jump, label):
        """
        Remove all connections to labels that just jump to another label,
        with direct connections to that label.
        Example to check: D01P11A/um2402.ssb
        - RULE: [Any, Label1, Jump[in=1,out=1], Label2] -> [Any, Label2]
        """
        outs = g.incident(jump, OUT)
        assert len(outs) == 1
        ov = g.es[outs[0]].target_vertex
        if isinstance(ov['op'], SsbLabel):
            # The jump target is just another label, redirect previous label to this one.
            ins = g.incident(label, IN)
            for in_edge_id in ins:
                old_in_edge = g.es[in_edge_id]
                attr = old_in_edge.attributes()
                iv = old_in_edge.source
                # Create a new edge between the target label and the old entry point
                g.add_edge(iv, ov, **attr)
            g.delete_edges(ins)
            return [jump.index, label.index]
        return []

    def group_objs(self):
        pass

    def group_switch_cases(self):
        pass

    def group_switches(self):
        pass

    def build_branches(self):
        """
        Marks "ifs" in the graph, based on Branch* opcodes.
        Examples to check:
        - unionall 73 for if-only,
        - 10 for else-only,
        - 274 for if-else w tail,
        - 90 for if-else w tail [2] and if-only [3]
        - complex: 89
        """
        for i, g in enumerate(self._graphs):
            vs_to_delete = []
            current_if_id = -1
            for v in g.vs:
                if isinstance(v['op'], SsbLabelJump) and v['op'].root.op_code.name in OPS_BRANCH.keys():
                    current_if_id += 1
                    # IS A BRANCH OPCODE
                    v['op'].add_marker(SsbIfStart(current_if_id))
                    self._update_vertex_style(v)
                    else_edge, if_edge = find_lowest_and_highest_out_edge(g, v, 'flow_level')
                    assert else_edge != if_edge
                    else_edge['is_else'] = True
                    self._update_edge_style(else_edge)

                    # Common end label
                    e_on_if_bef_end, e_on_else_bef_end = find_first_common_next_vertex_in_edges(g, else_edge.target_vertex, if_edge.target_vertex)
                    if e_on_if_bef_end is not None:
                        end_vertex = e_on_if_bef_end.target_vertex
                        v_on_if_bef_end = e_on_if_bef_end.source_vertex
                        v_on_else_bef_end = e_on_else_bef_end.source_vertex
                        if not isinstance(end_vertex['op'], SsbLabel):
                            # There's no real end, but a loop. TODO: This could lead to real problems...
                            continue
                        end_vertex['op'].add_marker(SsbIfEnd(current_if_id))
                        self._update_vertex_style(end_vertex)

                        # Remove the jumps before the common end label (if they exist), we don't need them anymore.
                        if isinstance(v_on_if_bef_end['op'], SsbLabelJump) and v_on_if_bef_end['op'].root.op_code.name == OP_JUMP:
                            vs_to_delete.append(v_on_if_bef_end.index)
                            e_before_jump_on_if = g.es[g.incident(v_on_if_bef_end, IN)[0]]
                            self._reconnect(g, e_before_jump_on_if.source, e_before_jump_on_if, end_vertex)

                        if isinstance(v_on_else_bef_end['op'], SsbLabelJump) and v_on_else_bef_end['op'].root.op_code.name == OP_JUMP:
                            vs_to_delete.append(v_on_else_bef_end.index)
                            e_before_jump_on_else = g.es[g.incident(v_on_else_bef_end, IN)[0]]
                            self._reconnect(g, e_before_jump_on_else.source, e_before_jump_on_else, end_vertex)

            g.delete_vertices(vs_to_delete)

    def group_branches(self):
        """
        Groups branches right next to each other in the else-path, that have the same if-path together (if x or y)
        Examples to check:
        - unionall 86 2+3
        :return:
        """

    def build_loops(self):
        pass

    def remove_label_markers(self):
        pass

    def _get_edges(self, g: Graph, rtn: List[SsbOperation], rtn_id: int, label_indices: Dict[int, int]):
        """
        Get the edges for the graph g by a list of SsbOperations. Will branch at SsbLabelJumps.
        """
        already_visited = set()
        self._get_edges__add_edge(g, rtn, rtn_id, label_indices, 0, already_visited)

        # Also collect left-over opcodes at the very end of a routine. For some routines there seems to be code
        # at the end that SEEMS unreachable, but we collect it anyway and try connect it from reverse with the first
        # ending opcode we can find
        op_code_idx = len(rtn) - 1
        # Not applicable for one-instruction routines.
        while op_code_idx > 1:
            if len(list(g.incident(op_code_idx, IN))) < 1:
                e = g.add_edge(op_code_idx - 1, op_code_idx, flow_level=0, label=None, is_else=False, op=None, loop=False)
                self._update_edge_style(e)
                v_op = g.vs[op_code_idx]['op']
                # Don't forget the labels
                if isinstance(v_op, SsbLabelJump) and v_op.label.routine_id == rtn_id and v_op.root.op_code.name != OP_JUMP:
                    is_loop = label_indices[v_op.label.id] < op_code_idx and len(g.incident(label_indices[v_op.label.id], IN)) > 0
                    g.add_edge(op_code_idx, label_indices[v_op.label.id], flow_level=1, label=None, is_else=False, op=None, loop=is_loop)
                    self._update_edge_style(e)
                op_code_idx -= 1
            else:
                break

    def _get_edges__add_edge(self,
                             g: Graph, rtn: List[SsbOperation], rtn_id: int, label_indices: Dict[int, int],
                             op_i: int, already_visited: Set[int], flow_level=0):
        if op_i in already_visited:
            return  # Loop
        already_visited.add(op_i)
        for flow_level, nxt in self._get_edges__get_next_for(rtn, rtn_id, flow_level, label_indices, op_i):
            e = g.add_edge(op_i, nxt, flow_level=flow_level, label=None, is_else=False, op=None, loop=False)
            if is_loop(g, g.vs[op_i], e):
                e['loop'] = True
            self._update_edge_style(e)
            self._get_edges__add_edge(g, rtn, rtn_id, label_indices, nxt, already_visited, flow_level)

    def _get_edges__get_next_for(self, rtn: List[SsbOperation], rtn_id: int, flow_level: int,
                                 label_indices: Dict[int, int], op_i: int) -> List[Tuple[int, int]]:
        """
        Returns a list of next opcodes to visit from this opcode and
        their flow level (flow_level for normal continue; flow_level + 1 for jump)
        """
        next_ops: List[Tuple[int, int]] = []

        op = rtn[op_i]
        real_op = op
        is_label_jump = False
        if isinstance(op, SsbLabelJump):
            real_op = op.root
            is_label_jump = True
        # If this is not a guaranteed jump or the last op_code in rtn, one possible branch is always just the next op:
        if len(rtn) > op_i + 1 and real_op.op_code.name not in OPS_THAT_END_CONTROL_FLOW:
            next_ops.append((flow_level, op_i + 1))
        # If this is a label jump, we can also continue at the label
        if is_label_jump and op.label.routine_id == rtn_id:
            next_ops.append((flow_level + 1, label_indices[op.label.id]))

        # If this would be the end but we are "Hold", then MAYBE there's still a statement after use, which we should
        # include, see notes at constant.
        if real_op.op_code.name == OP_HOLD and len(rtn) > op_i + 1:
            if rtn[op_i + 1].op_code.name in OPS_THAT_END_CONTROL_FLOW:
                next_ops.append((flow_level, op_i + 1))

        return next_ops

    @classmethod
    def _reconnect(cls, g, old_vertex, old_vertex_edge_to_remove, new_vertex_to_connect):
        attr = old_vertex_edge_to_remove.attributes()
        g.delete_edges(old_vertex_edge_to_remove)
        e = g.add_edge(old_vertex, new_vertex_to_connect, **attr)
        cls._update_edge_style(e)

    @staticmethod
    def _update_vertex_style(v):
        v['label'] = f"<{v['name']}>{v['op'].op_code.name}"
        if isinstance(v['op'], SsbLabel):
            v['style'] = 'striped'
            v['fillcolor'] = '#B446E3'
            v['shape'] = 'rectangle'
            if len(v['op'].markers) > 0:
                marker_str = ""
                v['fillcolor'] = ''
                for marker in v['op'].markers:
                    if isinstance(marker, SsbIfEnd):
                        v['fillcolor'] += '#A85400:'
                    marker_str += str(marker) + ";"
                marker_str = marker_str[:-1]
                v['fillcolor'] = v['fillcolor'][:-1]
                v['label'] += f" ({marker_str})"
        elif isinstance(v['op'], SsbLabelJump):
            v['style'] = 'filled'  # TODO: wedged not working...?
            v['fillcolor'] = '#38BCFF'
            v['shape'] = 'ellipse'
            if len(v['op'].markers) > 0:
                marker_str = ""
                v['fillcolor'] = ''
                for marker in v['op'].markers:
                    if isinstance(marker, SsbIfStart):
                        v['fillcolor'] += '#E36A00:'
                    marker_str += str(marker) + ";"
                marker_str = marker_str[:-1]
                v['fillcolor'] = v['fillcolor'][:-1]
                v['label'] += f" ({marker_str})"

    @staticmethod
    def _update_edge_style(e):
        e['color'] = 'black'
        e['label'] = str(e['flow_level'])
        if e['is_else']:
            e['label'] += ' <Else>'
        if e['loop']:
            e['color'] = 'red'
            e['label'] += ' <Loop>'
