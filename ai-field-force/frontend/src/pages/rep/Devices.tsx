import { useState, useEffect } from 'react';
import Layout from '../../components/Layout';
import { getDevices, revokeDevice } from '../../api/devices';
import { useDevice } from '../../hooks/useDevice';
import { useLang } from '../../context/LangContext';
import type { Device } from '../../types';

function platformIcon(platform: string) {
  const lower = platform.toLowerCase();
  if (lower.includes('android')) return '📱';
  if (lower.includes('ios') || lower.includes('iphone')) return '📱';
  if (lower.includes('windows')) return '💻';
  if (lower.includes('mac')) return '🖥️';
  return '🌐';
}

export default function Devices() {
  const { deviceId } = useDevice();
  const { t } = useLang();
  const [devices, setDevices] = useState<Device[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [revoking, setRevoking] = useState<string | null>(null);

  function timeAgo(dateStr: string): string {
    const diff = Date.now() - new Date(dateStr).getTime();
    const minutes = Math.floor(diff / 60_000);
    const hours = Math.floor(diff / 3_600_000);
    const days = Math.floor(diff / 86_400_000);
    if (minutes < 5) return t('time.active_now');
    if (hours < 1) return `${minutes}m ${t('time.ago')}`;
    if (days < 1) return `${hours}h ${t('time.ago')}`;
    return `${days}d ${t('time.ago')}`;
  }

  useEffect(() => {
    getDevices()
      .then(setDevices)
      .catch(() => setError('Failed to load devices.'))
      .finally(() => setLoading(false));
  }, []);

  async function handleRevoke(device_id: string) {
    if (!confirm(t('devices.revoke_confirm'))) return;
    setRevoking(device_id);
    try {
      await revokeDevice(device_id);
      setDevices((prev) => prev.filter((d) => d.device_id !== device_id));
    } catch {
      setError('Failed to revoke device.');
    } finally {
      setRevoking(null);
    }
  }

  return (
    <Layout>
      <div className="mb-5">
        <h1 className="page-header">{t('devices.title')}</h1>
        <p className="text-sm text-sage-500 mt-1">{t('devices.subtitle')}</p>
      </div>

      <div className="card p-4 mb-5 bg-forest-50 border-forest-200">
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-full bg-forest-100 flex items-center justify-center shrink-0">
            <span className="w-2.5 h-2.5 rounded-full bg-forest-500" />
          </div>
          <div>
            <p className="text-xs font-semibold text-forest-800">{t('devices.current_id')}</p>
            <p className="text-[11px] text-forest-600 font-mono break-all">{deviceId}</p>
          </div>
        </div>
      </div>

      {loading && (
        <div className="space-y-3 animate-pulse">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="card p-4">
              <div className="flex gap-3">
                <div className="w-10 h-10 rounded-xl bg-sage-100" />
                <div className="flex-1 space-y-2">
                  <div className="h-4 bg-sage-100 rounded w-1/2" />
                  <div className="h-3 bg-sage-100 rounded w-1/3" />
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {error && (
        <div className="card p-4 bg-clay-50 border-clay-100">
          <p className="text-sm text-clay-700 font-medium">{error}</p>
        </div>
      )}

      {!loading && !error && (
        <div className="space-y-3">
          {devices.length === 0 && (
            <div className="card p-8 text-center">
              <p className="text-sm text-sage-500">{t('reps.none')}</p>
            </div>
          )}
          {devices.map((device) => {
            const isCurrent = device.device_id === deviceId || device.is_current;
            return (
              <div
                key={device.device_id}
                className={`card p-4 ${isCurrent ? 'border-forest-200 bg-forest-50' : ''}`}
              >
                <div className="flex items-start gap-3">
                  <div className="w-10 h-10 rounded-xl bg-white border border-sage-100 flex items-center justify-center text-xl shrink-0">
                    {platformIcon(device.device_platform)}
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-0.5">
                      <span className="font-semibold text-sm text-forest-900 truncate">
                        {device.device_name}
                      </span>
                      {isCurrent && (
                        <span className="badge-green shrink-0">{t('devices.this_device')}</span>
                      )}
                    </div>
                    <p className="text-xs text-sage-500 capitalize">{device.device_platform}</p>
                    <p className="text-xs text-sage-400 mt-0.5">{timeAgo(device.last_seen)}</p>
                  </div>
                  {!isCurrent && (
                    <button
                      onClick={() => handleRevoke(device.device_id)}
                      disabled={revoking === device.device_id}
                      className="btn-danger text-xs py-1.5 px-3 shrink-0"
                    >
                      {revoking === device.device_id ? '...' : t('devices.revoke')}
                    </button>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </Layout>
  );
}