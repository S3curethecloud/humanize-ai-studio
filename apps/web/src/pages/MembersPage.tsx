import {
  useCallback,
  useEffect,
  useMemo,
  useState
} from "react";

import type {
  EnterpriseAccessContextState
} from "../app/useEnterpriseAccessContext";

import {
  addEnterpriseMember,
  changeEnterpriseMemberRole,
  listEnterpriseMembers,
  reactivateEnterpriseMember,
  removeEnterpriseMember,
  suspendEnterpriseMember,
  transferEnterpriseOwnership,
  type EnterpriseMember,
  type EnterpriseMembershipStatus,
  type EnterpriseWorkspaceRole
} from "../api/members";

interface MembersPageProps {
  accessContext: EnterpriseAccessContextState;
}

type AssignableRole = Exclude<
  EnterpriseWorkspaceRole,
  "owner"
>;

const ASSIGNABLE_ROLES: AssignableRole[] = [
  "admin",
  "editor",
  "reviewer",
  "viewer"
];

const STATUS_FILTERS: Array<
  EnterpriseMembershipStatus | "all"
> = [
  "all",
  "active",
  "suspended",
  "removed"
];

function generateMembershipId(): string {
  return `membership_${Date.now()}`;
}

function roleLabel(
  role: EnterpriseWorkspaceRole
): string {
  return role
    .split("_")
    .map(
      (segment) =>
        segment.charAt(0).toUpperCase() +
        segment.slice(1)
    )
    .join(" ");
}

function statusLabel(
  status: EnterpriseMembershipStatus
): string {
  return (
    status.charAt(0).toUpperCase() +
    status.slice(1)
  );
}

export default function MembersPage({
  accessContext
}: MembersPageProps) {
  const [members, setMembers] =
    useState<EnterpriseMember[]>([]);

  const [statusFilter, setStatusFilter] =
    useState<
      EnterpriseMembershipStatus | "all"
    >("all");

  const [newUserId, setNewUserId] =
    useState("");

  const [newRole, setNewRole] =
    useState<AssignableRole>("viewer");

  const [message, setMessage] =
    useState<string | null>(null);

  const [busy, setBusy] =
    useState(false);

  const canUse =
    accessContext.status === "connected" &&
    accessContext.workspaceId !== null &&
    accessContext.userId !== null;

  const permissions =
    accessContext.context?.permissions ?? [];

  const canRead =
    permissions.includes("members.read");

  const canInvite =
    permissions.includes("members.invite");

  const canAssignRole =
    permissions.includes(
      "members.role_assign"
    );

  const canRemove =
    permissions.includes("members.remove");

  const canTransferOwnership =
    permissions.includes(
      "workspace.transfer_ownership"
    );

  const currentUserId =
    accessContext.userId;

  const load = useCallback(async () => {
    if (
      !canUse ||
      accessContext.workspaceId === null ||
      accessContext.userId === null ||
      !canRead
    ) {
      setMembers([]);
      return;
    }

    setBusy(true);

    try {
      const result =
        await listEnterpriseMembers({
          workspaceId:
            accessContext.workspaceId,
          actorUserId:
            accessContext.userId,
          status:
            statusFilter === "all"
              ? undefined
              : statusFilter
        });

      setMembers(result.members);
      setMessage(null);
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to load members."
      );
    } finally {
      setBusy(false);
    }
  }, [
    accessContext.userId,
    accessContext.workspaceId,
    canRead,
    canUse,
    statusFilter
  ]);

  useEffect(() => {
    void load();
  }, [load]);

  const activeOwnerCount =
    useMemo(
      () =>
        members.filter(
          ({ membership }) =>
            membership.role === "owner" &&
            membership.status === "active"
        ).length,
      [members]
    );

  async function handleAddMember() {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    const userId = newUserId.trim();

    if (userId === "") {
      setMessage(
        "User ID is required."
      );
      return;
    }

    setBusy(true);
    setMessage(
      "Adding governed workspace membership."
    );

    try {
      await addEnterpriseMember({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        membershipId:
          generateMembershipId(),
        userId,
        role: newRole
      });

      setNewUserId("");
      await load();

      setMessage(
        "Workspace member added."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to add member."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRoleChange(
    member: EnterpriseMember,
    role: AssignableRole
  ) {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    setBusy(true);

    try {
      await changeEnterpriseMemberRole({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        userId:
          member.membership.user_id,
        role
      });

      await load();

      setMessage(
        "Member role updated."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to change member role."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleSuspend(
    member: EnterpriseMember
  ) {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    setBusy(true);

    try {
      await suspendEnterpriseMember({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        userId:
          member.membership.user_id
      });

      await load();

      setMessage(
        "Member suspended."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to suspend member."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleReactivate(
    member: EnterpriseMember
  ) {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    setBusy(true);

    try {
      await reactivateEnterpriseMember({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        userId:
          member.membership.user_id
      });

      await load();

      setMessage(
        "Member reactivated."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to reactivate member."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRemove(
    member: EnterpriseMember
  ) {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    setBusy(true);

    try {
      await removeEnterpriseMember({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        userId:
          member.membership.user_id
      });

      await load();

      setMessage(
        "Member removed."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to remove member."
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleTransferOwnership(
    member: EnterpriseMember
  ) {
    if (
      accessContext.workspaceId === null ||
      accessContext.userId === null
    ) {
      return;
    }

    setBusy(true);

    try {
      await transferEnterpriseOwnership({
        workspaceId:
          accessContext.workspaceId,
        actorUserId:
          accessContext.userId,
        targetUserId:
          member.membership.user_id
      });

      await load();

      setMessage(
        "Workspace ownership transferred."
      );
    } catch (error) {
      setMessage(
        error instanceof Error
          ? error.message
          : "Unable to transfer ownership."
      );
    } finally {
      setBusy(false);
    }
  }

  if (!canUse) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>
              Members & Roles unavailable
            </h1>

            <p>
              Canonical workspace access
              context is required before
              membership administration.
            </p>
          </div>
        </section>
      </div>
    );
  }

  if (!canRead) {
    return (
      <div className="enterprise-page">
        <section className="enterprise-analytics-state">
          <div>
            <h1>
              Members & Roles unavailable
            </h1>

            <p>
              The current workspace
              membership does not grant
              members.read.
            </p>
          </div>
        </section>
      </div>
    );
  }

  return (
    <div className="enterprise-page">
      <section className="enterprise-analytics-hero">
        <div>
          <p className="enterprise-eyebrow">
            Admin · Members & Roles
          </p>

          <h1>
            Workspace members
          </h1>

          <p className="enterprise-hero__description">
            Inspect and administer canonical
            enterprise workspace memberships,
            roles, lifecycle state, and ownership.
          </p>
        </div>

        <button
          type="button"
          className="enterprise-secondary-button"
          disabled={busy}
          onClick={() => void load()}
        >
          Refresh members
        </button>
      </section>

      {message && (
        <section className="enterprise-analytics-state">
          <div>
            <p>{message}</p>
          </div>
        </section>
      )}

      <section className="enterprise-dashboard-section">
        <div className="enterprise-section__heading">
          <div>
            <p className="enterprise-eyebrow">
              Membership inventory
            </p>

            <h2>
              Governed access
            </h2>
          </div>

          <p>
            Active owners: {activeOwnerCount}
          </p>
        </div>

        <div className="source-workspace">
          <label>
            Status
            <select
              value={statusFilter}
              disabled={busy}
              onChange={(event) =>
                setStatusFilter(
                  event.target.value as
                    EnterpriseMembershipStatus |
                    "all"
                )
              }
            >
              {STATUS_FILTERS.map(
                (status) => (
                  <option
                    key={status}
                    value={status}
                  >
                    {status === "all"
                      ? "All"
                      : statusLabel(status)}
                  </option>
                )
              )}
            </select>
          </label>
        </div>

        {canInvite && (
          <div className="source-workspace">
            <label>
              Existing user ID
              <input
                type="text"
                value={newUserId}
                disabled={busy}
                onChange={(event) =>
                  setNewUserId(
                    event.target.value
                  )
                }
              />
            </label>

            <label>
              Role
              <select
                value={newRole}
                disabled={busy}
                onChange={(event) =>
                  setNewRole(
                    event.target.value as
                      AssignableRole
                  )
                }
              >
                {ASSIGNABLE_ROLES.map(
                  (role) => (
                    <option
                      key={role}
                      value={role}
                    >
                      {roleLabel(role)}
                    </option>
                  )
                )}
              </select>
            </label>

            <button
              type="button"
              className="enterprise-primary-button"
              disabled={busy}
              onClick={() =>
                void handleAddMember()
              }
            >
              Add member
            </button>
          </div>
        )}

        {members.length === 0 ? (
          <p>
            No memberships match the
            current filter.
          </p>
        ) : (
          <div className="enterprise-table-wrap">
            <table className="enterprise-table">
              <thead>
                <tr>
                  <th>User</th>
                  <th>Role</th>
                  <th>Status</th>
                  <th>Permissions</th>
                  <th>Actions</th>
                </tr>
              </thead>

              <tbody>
                {members.map((member) => {
                  const {
                    membership,
                    effective_permissions
                  } = member;

                  const isOwner =
                    membership.role === "owner";

                  const isCurrentUser =
                    membership.user_id ===
                    currentUserId;

                  return (
                    <tr
                      key={
                        membership.membership_id
                      }
                    >
                      <td>
                        <strong>
                          {membership.user_id}
                        </strong>

                        <br />

                        <small>
                          {
                            membership.membership_id
                          }
                        </small>
                      </td>

                      <td>
                        {canAssignRole &&
                        !isOwner &&
                        membership.status !==
                          "removed" ? (
                          <select
                            value={membership.role}
                            disabled={busy}
                            onChange={(event) =>
                              void handleRoleChange(
                                member,
                                event.target.value as
                                  AssignableRole
                              )
                            }
                          >
                            {ASSIGNABLE_ROLES.map(
                              (role) => (
                                <option
                                  key={role}
                                  value={role}
                                >
                                  {
                                    roleLabel(
                                      role
                                    )
                                  }
                                </option>
                              )
                            )}
                          </select>
                        ) : (
                          roleLabel(
                            membership.role
                          )
                        )}
                      </td>

                      <td>
                        {statusLabel(
                          membership.status
                        )}
                      </td>

                      <td>
                        {
                          effective_permissions
                            .length
                        }
                      </td>

                      <td>
                        {canRemove &&
                          !isOwner &&
                          membership.status ===
                            "active" && (
                            <button
                              type="button"
                              className="enterprise-secondary-button"
                              disabled={busy}
                              onClick={() =>
                                void handleSuspend(
                                  member
                                )
                              }
                            >
                              Suspend
                            </button>
                          )}

                        {canRemove &&
                          !isOwner &&
                          membership.status ===
                            "suspended" && (
                            <button
                              type="button"
                              className="enterprise-secondary-button"
                              disabled={busy}
                              onClick={() =>
                                void handleReactivate(
                                  member
                                )
                              }
                            >
                              Reactivate
                            </button>
                          )}

                        {canRemove &&
                          !isOwner &&
                          membership.status !==
                            "removed" && (
                            <button
                              type="button"
                              className="enterprise-secondary-button"
                              disabled={busy}
                              onClick={() =>
                                void handleRemove(
                                  member
                                )
                              }
                            >
                              Remove
                            </button>
                          )}

                        {canTransferOwnership &&
                          !isOwner &&
                          !isCurrentUser &&
                          membership.status ===
                            "active" && (
                            <button
                              type="button"
                              className="enterprise-secondary-button"
                              disabled={busy}
                              onClick={() =>
                                void handleTransferOwnership(
                                  member
                                )
                              }
                            >
                              Transfer ownership
                            </button>
                          )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>
    </div>
  );
}
