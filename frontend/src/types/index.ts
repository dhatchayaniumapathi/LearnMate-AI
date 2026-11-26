/**
 * Core frontend type definitions.
 */

export interface NavItem {
  id: string;
  name: string;
  iconName: string;
  badge?: string;
  description: string;
}

export interface MetricCardData {
  title: string;
  value: string;
  change?: string;
  icon: string;
}

export interface SystemHealthStatus {
  status: 'ok' | 'degraded' | 'standby';
  service?: string;
  version?: string;
  databaseConnected?: boolean;
}
