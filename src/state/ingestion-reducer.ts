import {
  LINKEDIN_MODULES,
  type FileParseResult,
  type LinkedInModule,
  type MappingOverrides,
  type ModuleAssignment,
  type ParseError,
  type StandardField,
} from "@/domain/linkedin";
import {
  findDuplicateModules,
  findRepeatedDetectedModules,
  hasAllRequiredModules,
} from "@/data-processing/readiness";

export type UploadStatus = "idle" | "parsing" | "parsed" | "error";

export interface UploadSlotState {
  module: LinkedInModule;
  status: UploadStatus;
  file: File | null;
  result: FileParseResult | null;
  error: ParseError | null;
  confirmed: boolean;
  mappingOverrides: MappingOverrides;
  mappingDirty: boolean;
}

export interface IngestionState {
  mode: "uploaded" | "mock" | null;
  slots: Record<LinkedInModule, UploadSlotState>;
  activeSlot: LinkedInModule | null;
  analysisReady: boolean;
  qualityWarningsAcknowledged: boolean;
  announcement: string;
}

export type IngestionAction =
  | {
      type: "PARSE_STARTED";
      module: LinkedInModule;
      file: File;
      preserveMappings: boolean;
    }
  | {
      type: "PARSE_SUCCEEDED";
      module: LinkedInModule;
      result: FileParseResult;
    }
  | {
      type: "PARSE_FAILED";
      module: LinkedInModule;
      error: ParseError;
    }
  | {
      type: "LOAD_MOCK";
      results: Record<LinkedInModule, FileParseResult>;
    }
  | { type: "REMOVE_FILE"; module: LinkedInModule }
  | { type: "SET_ACTIVE_SLOT"; module: LinkedInModule }
  | { type: "CONFIRM_MODULE"; module: LinkedInModule }
  | {
      type: "UPDATE_MAPPING";
      module: LinkedInModule;
      key: string;
      field: StandardField | null | undefined;
    }
  | { type: "MARK_ANALYSIS_READY" }
  | { type: "ACKNOWLEDGE_QUALITY_WARNINGS" }
  | { type: "RESET" };

function createEmptySlot(module: LinkedInModule): UploadSlotState {
  return {
    module,
    status: "idle",
    file: null,
    result: null,
    error: null,
    confirmed: false,
    mappingOverrides: {},
    mappingDirty: false,
  };
}

export function createInitialIngestionState(): IngestionState {
  return {
    mode: null,
    slots: {
      followers: createEmptySlot("followers"),
      visitors: createEmptySlot("visitors"),
      content: createEmptySlot("content"),
    },
    activeSlot: null,
    analysisReady: false,
    qualityWarningsAcknowledged: false,
    announcement: "请选择三类 LinkedIn 导出文件，或载入脱敏示例数据。",
  };
}

function replaceSlot(
  state: IngestionState,
  module: LinkedInModule,
  slot: UploadSlotState,
): IngestionState["slots"] {
  return { ...state.slots, [module]: slot };
}

export function ingestionReducer(
  state: IngestionState,
  action: IngestionAction,
): IngestionState {
  if (action.type === "RESET") {
    return createInitialIngestionState();
  }

  if (action.type === "LOAD_MOCK") {
    return {
      mode: "mock",
      slots: {
        followers: {
          ...createEmptySlot("followers"),
          status: "parsed",
          result: action.results.followers,
          confirmed: true,
        },
        visitors: {
          ...createEmptySlot("visitors"),
          status: "parsed",
          result: action.results.visitors,
          confirmed: true,
        },
        content: {
          ...createEmptySlot("content"),
          status: "parsed",
          result: action.results.content,
          confirmed: true,
        },
      },
      activeSlot: "followers",
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: "已载入完全虚构的脱敏示例数据，三个模块已确认。",
    };
  }

  if (action.type === "PARSE_STARTED") {
    const baseState =
      state.mode === "mock" ? createInitialIngestionState() : state;
    const previous = baseState.slots[action.module];

    return {
      ...baseState,
      mode: "uploaded",
      slots: replaceSlot(baseState, action.module, {
        ...previous,
        status: "parsing",
        file: action.file,
        result: action.preserveMappings ? previous.result : null,
        error: null,
        confirmed: false,
        mappingOverrides: action.preserveMappings
          ? previous.mappingOverrides
          : {},
        mappingDirty: false,
      }),
      activeSlot: action.module,
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: `正在安全解析 ${action.file.name}。`,
    };
  }

  if (action.type === "PARSE_SUCCEEDED") {
    const previous = state.slots[action.module];
    return {
      ...state,
      slots: replaceSlot(state, action.module, {
        ...previous,
        status: "parsed",
        result: action.result,
        error: null,
        confirmed: false,
        mappingDirty: false,
      }),
      activeSlot: action.module,
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: `${action.result.file.name} 解析完成，请确认识别结果。`,
    };
  }

  if (action.type === "PARSE_FAILED") {
    const previous = state.slots[action.module];
    return {
      ...state,
      slots: replaceSlot(state, action.module, {
        ...previous,
        status: "error",
        result: null,
        error: action.error,
        confirmed: false,
      }),
      activeSlot: action.module,
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: action.error.message,
    };
  }

  if (action.type === "REMOVE_FILE") {
    return {
      ...state,
      slots: replaceSlot(
        state,
        action.module,
        createEmptySlot(action.module),
      ),
      activeSlot:
        state.activeSlot === action.module ? null : state.activeSlot,
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: `已移除 ${action.module} 文件。`,
    };
  }

  if (action.type === "SET_ACTIVE_SLOT") {
    return {
      ...state,
      activeSlot: action.module,
      analysisReady: false,
      qualityWarningsAcknowledged: false,
    };
  }

  if (action.type === "CONFIRM_MODULE") {
    const previous = state.slots[action.module];
    if (!previous.result?.canProceed || previous.mappingDirty) {
      return state;
    }

    return {
      ...state,
      slots: replaceSlot(state, action.module, {
        ...previous,
        confirmed: true,
      }),
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: `已确认 ${action.module} 的识别与字段映射。`,
    };
  }

  if (action.type === "UPDATE_MAPPING") {
    const previous = state.slots[action.module];
    const mappingOverrides = { ...previous.mappingOverrides };

    if (action.field === undefined) {
      delete mappingOverrides[action.key];
    } else {
      mappingOverrides[action.key] = action.field;
    }

    return {
      ...state,
      slots: replaceSlot(state, action.module, {
        ...previous,
        mappingOverrides,
        mappingDirty: true,
        confirmed: false,
      }),
      analysisReady: false,
      qualityWarningsAcknowledged: false,
      announcement: "字段映射已修改，请应用后重新校验。",
    };
  }

  if (action.type === "ACKNOWLEDGE_QUALITY_WARNINGS") {
    return {
      ...state,
      qualityWarningsAcknowledged: true,
      announcement: "已确认非阻断数据质量警告。",
    };
  }

  if (action.type === "MARK_ANALYSIS_READY") {
    return {
      ...state,
      analysisReady: true,
      qualityWarningsAcknowledged: false,
      announcement: "Analysis Snapshot 已生成。",
    };
  }

  return state;
}

function primaryDetectedModule(
  slot: UploadSlotState,
): LinkedInModule | null {
  if (!slot.result || slot.result.detectedModules.length !== 1) {
    return null;
  }
  return slot.result.detectedModules[0];
}

export function getModuleAssignments(
  state: IngestionState,
): ModuleAssignment[] {
  return LINKEDIN_MODULES.map((module) => ({
    slot: module,
    detectedModule: primaryDetectedModule(state.slots[module]),
    confirmed: state.slots[module].confirmed,
  }));
}

export function getRepeatedModules(
  state: IngestionState,
): LinkedInModule[] {
  return findRepeatedDetectedModules(getModuleAssignments(state));
}

export function canStartAnalysis(state: IngestionState): boolean {
  const assignments = getModuleAssignments(state);
  return (
    findDuplicateModules(assignments).length === 0 &&
    findRepeatedDetectedModules(assignments).length === 0 &&
    hasAllRequiredModules(assignments) &&
    LINKEDIN_MODULES.every(
      (module) => state.slots[module].result?.canProceed,
    )
  );
}
