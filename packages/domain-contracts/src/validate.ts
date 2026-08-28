import { Ajv, type ValidateFunction } from "ajv";

import activationRequestSchema from "../schemas/activation-request.v1.schema.json";
import approvalSchema from "../schemas/approval.v1.schema.json";
import approvedContentPackageSchema from "../schemas/approved-content-package.v1.schema.json";
import connectorErrorSchema from "../schemas/connector-error.v1.schema.json";
import runEventSchema from "../schemas/run-event.v1.schema.json";
import runSchema from "../schemas/run.v1.schema.json";
import taskSchema from "../schemas/task.v1.schema.json";
import toolCallSchema from "../schemas/tool-call.v1.schema.json";

export const CONTRACT_NAMES = [
  "run.v1",
  "run-event.v1",
  "task.v1",
  "approval.v1",
  "tool-call.v1",
  "approved-content-package.v1",
  "activation-request.v1",
  "connector-error.v1",
] as const;

export type ContractName = (typeof CONTRACT_NAMES)[number];

const SCHEMAS: Record<ContractName, object> = {
  "run.v1": runSchema,
  "run-event.v1": runEventSchema,
  "task.v1": taskSchema,
  "approval.v1": approvalSchema,
  "tool-call.v1": toolCallSchema,
  "approved-content-package.v1": approvedContentPackageSchema,
  "activation-request.v1": activationRequestSchema,
  "connector-error.v1": connectorErrorSchema,
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
