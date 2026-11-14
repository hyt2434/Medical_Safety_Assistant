/** Demo identity model aligned with the 35-table access ERD.
 * Route checks in the UI are not server authorization. */

export type RoleCode =
  "patient" | "hcp" | "medical_reviewer" | "admin" | "technical_support";

export type Permission =
  | "patient.workspace"
  | "clinical.case_review"
  | "catalog.review"
  | "catalog.edit"
  | "staff.directory"
  | "operations.queue"
  | "admin.accounts"
  | "admin.roles"
  | "admin.audit";

export type Account = {
  id: string;
  email: string;
  fullName: string;
  phone: string;
  accountStatus: "active" | "locked";
};

export type RoleGrant = {
  userId: string;
  roleCode: RoleCode;
  grantedAt: string;
  expiresAt: string | null;
  revokedAt: string | null;
};

export type ProfessionalProfile = {
  userId: string;
  professionalType: string;
  licenseNumber: string;
  specialty: string;
  verificationStatus: "verified" | "pending";
};

export type StaffProfile = {
  userId: string;
  employeeCode: string;
  department: string;
  jobTitle: string;
  employmentStatus: "active" | "leave";
};

export type CareRelationship = {
  id: string;
  patientUserId: string;
  professionalUserId: string;
  relationshipType: string;
  status: "active" | "ended";
};

export type AuditEvent = {
  id: string;
  actorUserId: string | null;
  actionCode: string;
  targetType: string;
  targetId: string;
  success: boolean;
  occurredAt: string;
};

export type DataReviewItem = {
  id: string;
  title: string;
  status: "pending" | "in-review" | "released";
  value: string;
  note: string;
};

export type SupportTicket = {
  id: string;
  title: string;
  status: "open" | "doing" | "done";
  detail: string;
};

export const rolePermissions: Record<RoleCode, Permission[]> = {
  patient: ["patient.workspace"],
  hcp: ["clinical.case_review"],
  medical_reviewer: ["clinical.case_review", "catalog.review", "catalog.edit"],
  admin: ["staff.directory", "admin.accounts", "admin.roles", "admin.audit"],
  technical_support: ["staff.directory", "operations.queue"],
};

export const roleLabel: Record<RoleCode, string> = {
  patient: "Người dùng",
  hcp: "HCP",
  medical_reviewer: "Phản biện dữ liệu",
  admin: "Quản trị",
  technical_support: "Hỗ trợ kỹ thuật",
};

export const demoAccounts: Account[] = [
  {
    id: "u-patient",
    email: "mai.demo@example.com",
    fullName: "Trần Thị Mai",
    phone: "",
    accountStatus: "active",
  },
  {
    id: "u-hcp",
    email: "an.demo@example.com",
    fullName: "Lê Minh An",
    phone: "",
    accountStatus: "active",
  },
  {
    id: "u-reviewer",
    email: "huy.demo@example.com",
    fullName: "Phạm Quốc Huy",
    phone: "",
    accountStatus: "active",
  },
  {
    id: "u-admin",
    email: "ha.demo@example.com",
    fullName: "Nguyễn Thu Hà",
    phone: "",
    accountStatus: "active",
  },
  {
    id: "u-support",
    email: "khoa.demo@example.com",
    fullName: "Đỗ Văn Khoa",
    phone: "",
    accountStatus: "active",
  },
];

export const demoGrants: RoleGrant[] = [
  {
    userId: "u-patient",
    roleCode: "patient",
    grantedAt: "2026-09-01T08:00:00+07:00",
    expiresAt: null,
    revokedAt: null,
  },
  {
    userId: "u-hcp",
    roleCode: "hcp",
    grantedAt: "2026-09-01T08:00:00+07:00",
    expiresAt: null,
    revokedAt: null,
  },
  {
    userId: "u-reviewer",
    roleCode: "medical_reviewer",
    grantedAt: "2026-09-01T08:00:00+07:00",
    expiresAt: null,
    revokedAt: null,
  },
  {
    userId: "u-admin",
    roleCode: "admin",
    grantedAt: "2026-09-01T08:00:00+07:00",
    expiresAt: null,
    revokedAt: null,
  },
  {
    userId: "u-support",
    roleCode: "technical_support",
    grantedAt: "2026-09-01T08:00:00+07:00",
    expiresAt: null,
    revokedAt: null,
  },
];

export const demoProfessionalProfiles: ProfessionalProfile[] = [
  {
    userId: "u-hcp",
    professionalType: "pharmacist",
    licenseNumber: "CCHN-DEMO-01",
    specialty: "Dược lâm sàng",
    verificationStatus: "pending",
  },
  {
    userId: "u-reviewer",
    professionalType: "pharmacist",
    licenseNumber: "CCHN-DEMO-02",
    specialty: "Thẩm định dữ liệu dược",
    verificationStatus: "pending",
  },
];

export const demoStaffProfiles: StaffProfile[] = [
  {
    userId: "u-admin",
    employeeCode: "NS-ADMIN-01",
    department: "Quản trị hệ thống",
    jobTitle: "Quản trị viên",
    employmentStatus: "active",
  },
  {
    userId: "u-support",
    employeeCode: "NS-HT-01",
    department: "Hỗ trợ kỹ thuật",
    jobTitle: "Nhân viên vận hành",
    employmentStatus: "active",
  },
];

export const demoCareRelationships: CareRelationship[] = [
  {
    id: "care-demo-1",
    patientUserId: "u-patient",
    professionalUserId: "u-hcp",
    relationshipType: "medication_review",
    status: "active",
  },
];

export const demoDataReviews: DataReviewItem[] = [
  {
    id: "DR-01",
    title: "Ánh xạ Getzome Capsules",
    status: "pending",
    value: "Omeprazole",
    note: "",
  },
  {
    id: "DR-02",
    title: "Hàm lượng Clopidogrel mẫu",
    status: "in-review",
    value: "75 mg",
    note: "Chờ đối chiếu nguồn",
  },
];

export const demoTickets: SupportTicket[] = [
  {
    id: "OP-01",
    title: "Ảnh toa chưa vào hàng xử lý",
    status: "open",
    detail: "Phiên mẫu báo đã chọn ảnh nhưng chưa có bản ghi intake.",
  },
  {
    id: "OP-02",
    title: "Nguồn DAV chưa có gói dữ liệu",
    status: "doing",
    detail: "Trang nguồn vẫn ở trạng thái chưa kết nối.",
  },
];

export const accountForContext: Record<RoleCode, string> = {
  patient: "u-patient",
  hcp: "u-hcp",
  medical_reviewer: "u-reviewer",
  admin: "u-admin",
  technical_support: "u-support",
};

export function grantIsOpen(grant: RoleGrant, at = Date.now()) {
  if (grant.revokedAt) return false;
  if (grant.expiresAt && new Date(grant.expiresAt).getTime() <= at)
    return false;
  return true;
}

export function openGrants(grants: RoleGrant[], userId: string) {
  return grants.filter(
    (grant) => grant.userId === userId && grantIsOpen(grant),
  );
}

export function permissionsFor(grants: RoleGrant[], userId: string) {
  const codes = new Set<Permission>();
  for (const grant of openGrants(grants, userId)) {
    for (const permission of rolePermissions[grant.roleCode])
      codes.add(permission);
  }
  return [...codes];
}

export function workspaceFor(context: RoleCode | null) {
  if (context === "hcp" || context === "medical_reviewer") return "/hcp";
  if (context === "admin") return "/admin";
  if (context === "technical_support") return "/staff";
  if (context === "patient") return "/dashboard";
  return "/login";
}

export function initials(name: string) {
  const parts = name.trim().split(/\s+/).filter(Boolean);
  const first = parts[0]?.[0] ?? "";
  const last = parts.length > 1 ? (parts.at(-1)?.[0] ?? "") : "";
  return `${first}${last}`.toLocaleUpperCase("vi") || "•";
}
