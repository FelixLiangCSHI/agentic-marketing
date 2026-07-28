import {
  LINKEDIN_MODULES,
  type LinkedInModule,
  type ModuleAssignment,
} from "@/domain/linkedin";

export function findDuplicateModules(
  assignments: readonly ModuleAssignment[],
): LinkedInModule[] {
  return LINKEDIN_MODULES.filter((module) => {
    const count = assignments.filter(
      (assignment) =>
        assignment.confirmed && assignment.detectedModule === module,
    ).length;
    return count > 1;
  });
}

export function findRepeatedDetectedModules(
  assignments: readonly ModuleAssignment[],
): LinkedInModule[] {
  return LINKEDIN_MODULES.filter((module) => {
    const count = assignments.filter(
      (assignment) => assignment.detectedModule === module,
    ).length;
    return count > 1;
  });
}

export function hasAllRequiredModules(
  assignments: readonly ModuleAssignment[],
): boolean {
  if (findDuplicateModules(assignments).length > 0) {
    return false;
  }

  return LINKEDIN_MODULES.every((module) =>
    assignments.some(
      (assignment) =>
        assignment.slot === module &&
        assignment.confirmed &&
        assignment.detectedModule === module,
    ),
  );
}
