/**
 * 兼容 Adapter：把现有 `src/domain/` 的本地类型桥接到
 * `packages/domain-contracts/` 中的 v1 跨语言契约。
 *
 * 原则（Phase 01 / Subphase 02）：
 * - 不移动、不重写现有 `src/domain/` 类型；现有代码继续使用本地类型。
 * - 新生产代码消费契约类型时，只经由本 Adapter，不做自由文本状态转换。
 */
import type { ApprovalStatus } from "@/domain/strategy";

import type { ContractApprovalStatus } from "../../packages/domain-contracts/src/types";
import {
  validateContract,
  type ContractName,
  type ContractValidationResult,
} from "../../packages/domain-contracts/src/validate";

export type {
  ActivationRequestV1,
  ApprovalV1,
  ApprovedContentPackageV1,
  ConnectorErrorV1,
  ContractApprovalStatus,
  RunEventV1,
  RunV1,
  TaskV1,
  ToolCallV1,
} from "../../packages/domain-contracts/src/types";
export {
  CONTRACT_NAMES,
  validateContract,
  type ContractName,
  type ContractValidationResult,
} from "../../packages/domain-contracts/src/validate";

const LOCAL_TO_CONTRACT_APPROVAL_STATUS: Record<
  ApprovalStatus,
  ContractApprovalStatus
> = {
  draft: "PENDING",
  approved: "APPROVED",
  revision_requested: "REJECTED",
  rejected: "REJECTED",
};

/**
 * 把本地审批状态映射为契约审批状态。
 * 注意：`revision_requested` 与 `rejected` 都映射为 `REJECTED`；
 * 契约层通过重新发起 Approval 表达返工，不保留自由文本状态。
 */
export function toContractApprovalStatus(
  status: ApprovalStatus,
): ContractApprovalStatus {
  return LOCAL_TO_CONTRACT_APPROVAL_STATUS[status];
}

/** 运行时按 v1 契约校验任意文档；供服务端边界使用。 */
export function assertContractDocument(
  name: ContractName,
  document: unknown,
): ContractValidationResult {
  return validateContract(name, document);
}
