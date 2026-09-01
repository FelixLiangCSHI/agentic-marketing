import { Ajv, type ValidateFunction } from "ajv";

import activationRequestSchema from "../schemas/activation-request.v1.schema.json";
import approvalSchema from "../schemas/approval.v1.schema.json";
import approvedContentPackageSchema from "../schemas/approved-content-package.v1.schema.json";
import campaignProposalSchema from "../schemas/campaign-proposal.v1.schema.json";
import connectorErrorSchema from "../schemas/connector-error.v1.schema.json";
import contentRequestSchema from "../schemas/content-request.v1.schema.json";
import productChangeSchema from "../schemas/product-change.v1.schema.json";
import productClaimSchema from "../schemas/product-claim.v1.schema.json";
import productDocumentSchema from "../schemas/product-document.v1.schema.json";
import runEventSchema from "../schemas/run-event.v1.schema.json";
import runSchema from "../schemas/run.v1.schema.json";
import taskSchema from "../schemas/task.v1.schema.json";
import toolCallSchema from "../schemas/tool-call.v1.schema.json";
import type {
  ActivationRequestV1,
  ApprovalV1,
  ApprovedContentPackageV1,
  CampaignProposalV1,
  ConnectorErrorV1,
  ContentRequestV1,
  ProductChangeV1,
  ProductClaimV1,
  ProductDocumentV1,
  RunEventV1,
  RunV1,
  TaskV1,
  ToolCallV1,
} from "./types";

export const CONTRACT_NAMES = [
  "run.v1",
  "run-event.v1",
  "task.v1",
  "approval.v1",
  "tool-call.v1",
  "approved-content-package.v1",
  "campaign-proposal.v1",
  "activation-request.v1",
  "connector-error.v1",
  "content-request.v1",
  "product-document.v1",
  "product-claim.v1",
  "product-change.v1",
] as const;

export type ContractName = (typeof CONTRACT_NAMES)[number];

const SCHEMAS: Record<ContractName, object> = {
  "run.v1": runSchema,
  "run-event.v1": runEventSchema,
  "task.v1": taskSchema,
  "approval.v1": approvalSchema,
  "tool-call.v1": toolCallSchema,
  "approved-content-package.v1": approvedContentPackageSchema,
  "campaign-proposal.v1": campaignProposalSchema,
  "activation-request.v1": activationRequestSchema,
  "connector-error.v1": connectorErrorSchema,
  "content-request.v1": contentRequestSchema,
  "product-document.v1": productDocumentSchema,
  "product-claim.v1": productClaimSchema,
  "product-change.v1": productChangeSchema,
};

const ajv = new Ajv({ allErrors: true, strict: true });

const validators = new Map<ContractName, ValidateFunction>();

function getValidator(name: ContractName): ValidateFunction {
  let validator = validators.get(name);
  if (!validator) {
    validator = ajv.compile(SCHEMAS[name]);
    validators.set(name, validator);
  }
  return validator;
}

export interface ContractValidationResult {
  valid: boolean;
  errors: string[];
}

export function validateContract(
  name: ContractName,
  document: unknown,
): ContractValidationResult {
  const validator = getValidator(name);
  const valid = validator(document);
  if (valid) {
    return { valid: true, errors: [] };
  }
  const errors = (validator.errors ?? []).map(
    (error) => `${error.instancePath || "/"} ${error.message ?? "invalid"}`,
  );
  return { valid: false, errors };
}

// 编译期无法表达 JSON Schema 的 pattern/min-max/uniqueItems 等约束，
// 因此契约对象必须经运行时校验后才能获得 Validated<T> 品牌类型。
// 边界代码应要求 Validated<T>，避免拼装未经校验的契约对象。
declare const CONTRACT_VALIDATED: unique symbol;
export type Validated<T> = T & { readonly [CONTRACT_VALIDATED]: true };

export interface ContractTypeByName {
  "run.v1": RunV1;
  "run-event.v1": RunEventV1;
  "task.v1": TaskV1;
  "approval.v1": ApprovalV1;
  "tool-call.v1": ToolCallV1;
  "approved-content-package.v1": ApprovedContentPackageV1;
  "campaign-proposal.v1": CampaignProposalV1;
  "activation-request.v1": ActivationRequestV1;
  "connector-error.v1": ConnectorErrorV1;
  "content-request.v1": ContentRequestV1;
  "product-document.v1": ProductDocumentV1;
  "product-claim.v1": ProductClaimV1;
  "product-change.v1": ProductChangeV1;
}

export class ContractValidationError extends Error {
  readonly contract: ContractName;
  readonly issues: readonly string[];

  constructor(contract: ContractName, issues: readonly string[]) {
    super(`${contract} document is invalid: ${issues.join("; ")}`);
    this.name = "ContractValidationError";
    this.contract = contract;
    this.issues = issues;
  }
}

export function parseContract<Name extends ContractName>(
  name: Name,
  document: unknown,
): Validated<ContractTypeByName[Name]> {
  const result = validateContract(name, document);
  if (!result.valid) {
    throw new ContractValidationError(name, result.errors);
  }
  return document as Validated<ContractTypeByName[Name]>;
}

export function tryParseContract<Name extends ContractName>(
  name: Name,
  document: unknown,
):
  | { ok: true; value: Validated<ContractTypeByName[Name]> }
  | { ok: false; errors: string[] } {
  const result = validateContract(name, document);
  if (!result.valid) {
    return { ok: false, errors: result.errors };
  }
  return {
    ok: true,
    value: document as Validated<ContractTypeByName[Name]>,
  };
}
