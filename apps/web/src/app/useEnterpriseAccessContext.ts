import {
  useEffect,
  useState
} from "react";

import {
  EnterpriseAccessContextError,
  fetchEnterpriseAccessContext,
  type EnterpriseWorkspaceAccessContext
} from "../api/enterpriseContext";

export type EnterpriseAccessContextStatus =
  | "unconfigured"
  | "invalid"
  | "loading"
  | "connected"
  | "denied"
  | "error";

export interface EnterpriseAccessContextState {
  status: EnterpriseAccessContextStatus;
  workspaceId: string | null;
  userId: string | null;
  context: EnterpriseWorkspaceAccessContext | null;
  message: string | null;
}

const INITIAL_STATE: EnterpriseAccessContextState = {
  status: "unconfigured",
  workspaceId: null,
  userId: null,
  context: null,
  message: null
};

export function useEnterpriseAccessContext():
EnterpriseAccessContextState {
  const [state, setState] =
    useState<EnterpriseAccessContextState>(
      INITIAL_STATE
    );

  useEffect(() => {
    /*
     * UI1C explicit bootstrap only.
     *
     * These identifiers select an access context.
     * They do not establish authenticated identity
     * and must not be treated as a login/session.
     */
    const params = new URLSearchParams(
      window.location.search
    );

    const workspaceId =
      params.get("workspace_id")?.trim() ?? "";

    const userId =
      params.get("user_id")?.trim() ?? "";

    if (
      workspaceId === "" &&
      userId === ""
    ) {
      setState(INITIAL_STATE);
      return;
    }

    if (
      workspaceId === "" ||
      userId === ""
    ) {
      setState({
        status: "invalid",
        workspaceId:
          workspaceId || null,
        userId:
          userId || null,
        context: null,
        message:
          "Both workspace_id and user_id are required."
      });
      return;
    }

    const controller =
      new AbortController();

    setState({
      status: "loading",
      workspaceId,
      userId,
      context: null,
      message:
        "Resolving canonical workspace access context."
    });

    void fetchEnterpriseAccessContext({
      workspaceId,
      userId,
      signal: controller.signal
    })
      .then((context) => {
        setState({
          status: "connected",
          workspaceId,
          userId,
          context,
          message:
            "Workspace access context resolved by the server."
        });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) {
          return;
        }

        if (
          error instanceof
            EnterpriseAccessContextError &&
          error.status === 403
        ) {
          setState({
            status: "denied",
            workspaceId,
            userId,
            context: null,
            message:
              `Access denied: ${error.detail}`
          });
          return;
        }

        setState({
          status: "error",
          workspaceId,
          userId,
          context: null,
          message:
            error instanceof Error
              ? error.message
              : "Unable to resolve access context."
        });
      });

    return () => {
      controller.abort();
    };
  }, []);

  return state;
}
