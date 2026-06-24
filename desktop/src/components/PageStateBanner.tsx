import { useEffect, useState } from "react";
import { BACKEND_OFFLINE_ERROR, getHealth } from "../api/client";
import BackendOfflineNotice from "./BackendOfflineNotice";
import StateClarityRail from "./StateClarityRail";

const BACKEND_RECONNECT_POLL_MS = 3000;
const BACKEND_RECONNECT_MAX_ATTEMPTS = 20;
const BACKEND_RECONNECT_SESSION_KEY_PREFIX = "command_center_3_backend_reconnect_once:";

function reconnectSessionKey() {
  if (typeof window === "undefined") return BACKEND_RECONNECT_SESSION_KEY_PREFIX;
  return `${BACKEND_RECONNECT_SESSION_KEY_PREFIX}${window.location.pathname}${window.location.hash}`;
}

function markReconnectReloaded() {
  try {
    const key = reconnectSessionKey();
    if (window.sessionStorage.getItem(key) === "1") return false;
    window.sessionStorage.setItem(key, "1");
    return true;
  } catch {
    return true;
  }
}

export default function PageStateBanner({
  loading,
  error,
  empty,
  emptyTitle = "暂无缓存数据",
  emptyDetail = "当前页面只读取 FastAPI cache API；不会自动触发外部刷新。",
}: {
  loading?: boolean;
  error?: string;
  empty?: boolean;
  emptyTitle?: string;
  emptyDetail?: string;
}) {
  const isBackendOffline = Boolean(error?.includes(BACKEND_OFFLINE_ERROR));
  const [reconnectStatus, setReconnectStatus] = useState("idle");
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  useEffect(() => {
    if (!isBackendOffline) {
      setReconnectStatus("idle");
      setReconnectAttempts(0);
      return undefined;
    }

    let cancelled = false;
    let attempt = 0;
    let timer: number | undefined;
    const checkLocalHealth = () => {
      attempt += 1;
      setReconnectAttempts(attempt);
      setReconnectStatus("checking_local_health");
      void getHealth()
        .then((res) => {
          if (cancelled) return;
          const healthReady = res.ok === true && String(res.data?.status ?? "") === "ok";
          if (healthReady) {
            setReconnectStatus("local_fastapi_ready_reloading_once");
            if (markReconnectReloaded()) {
              window.setTimeout(() => window.location.reload(), 250);
            } else {
              setReconnectStatus("local_fastapi_ready_refresh_manually");
            }
            return;
          }
          setReconnectStatus(attempt >= BACKEND_RECONNECT_MAX_ATTEMPTS ? "waiting_for_local_launcher" : "waiting_for_local_fastapi");
        })
        .catch(() => {
          if (cancelled) return;
          setReconnectStatus(attempt >= BACKEND_RECONNECT_MAX_ATTEMPTS ? "waiting_for_local_launcher" : "waiting_for_local_fastapi");
        });
      if (attempt >= BACKEND_RECONNECT_MAX_ATTEMPTS && timer !== undefined) {
        window.clearInterval(timer);
      }
    };

    checkLocalHealth();
    timer = window.setInterval(checkLocalHealth, BACKEND_RECONNECT_POLL_MS);
    return () => {
      cancelled = true;
      if (timer !== undefined) window.clearInterval(timer);
    };
  }, [isBackendOffline]);

  if (loading) {
    return (
      <div className="page-state page-state-loading motion-surface" data-page-state="loading" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>正在读取本地缓存...</strong>
        <p>默认只调用 GET cache API，不触发 Tushare、DeepSeek、GitHub 或真实交易。</p>
        <StateClarityRail
          label="cache loading state"
          state="loading"
          steps={[
            { label: "cache", state: "active", detail: "GET" },
            { label: "ledger", state: "waiting", detail: "local" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  if (error) {
    return (
      <div className="page-state page-state-error motion-surface" data-page-state="error" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>缓存读取失败</strong>
        <BackendOfflineNotice error={error} />
        <p>{isBackendOffline ? "本地后端未连接；请按上方步骤使用本地启动器恢复连接。" : error}</p>
        {isBackendOffline ? (
          <p data-backend-reconnect-status={reconnectStatus}>
            自动接线检查：每 3 秒只读检查本机 FastAPI /health；检测到 ready 后刷新当前页一次。status={reconnectStatus} attempts={reconnectAttempts}；external_calls_triggered=false，不创建 task。
          </p>
        ) : null}
        <StateClarityRail
          label="cache error state"
          state="error"
          steps={[
            { label: "cache", state: "blocked", detail: "failed" },
            { label: "ledger", state: "waiting", detail: "review" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  if (empty) {
    return (
      <div className="page-state page-state-empty motion-surface" data-page-state="empty" data-motion-scope="cache_refresh_clarity" data-motion-purpose="state_change_confirmation">
        <strong>{emptyTitle}</strong>
        <p>{emptyDetail}</p>
        <StateClarityRail
          label="empty cache state"
          state="empty"
          steps={[
            { label: "cache", state: "waiting", detail: "empty" },
            { label: "ledger", state: "done", detail: "local" },
            { label: "boundary", state: "done", detail: "safe" }
          ]}
        />
      </div>
    );
  }

  return null;
}
