import type { ActionPlan } from "@/domain/action-plan";

export interface PlanEditorState {
  current: ActionPlan | null;
  history: ActionPlan[];
}

export type PlanEditorAction =
  | { type: "LOAD_PLAN"; plan: ActionPlan }
  | { type: "APPLY_REVISION"; plan: ActionPlan }
  | { type: "UNDO_LAST_REVISION" }
  | { type: "CLEAR_PLAN" };

export function createInitialPlanEditorState(): PlanEditorState {
  return { current: null, history: [] };
}

export function planEditorReducer(
  state: PlanEditorState,
  action: PlanEditorAction,
): PlanEditorState {
  if (action.type === "CLEAR_PLAN") {
    return createInitialPlanEditorState();
  }
  if (action.type === "LOAD_PLAN") {
    return { current: action.plan, history: [] };
  }
  if (action.type === "APPLY_REVISION") {
    return {
      current: action.plan,
      history: state.current ? [...state.history, state.current] : state.history,
    };
  }
  const previous = state.history.at(-1);
  if (!previous) {
    return state;
  }
  return {
    current: previous,
    history: state.history.slice(0, -1),
  };
}
