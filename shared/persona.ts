/**
 * Persona Mode System - First-class execution primitive
 *
 * PersonaMode determines:
 * - Access control and permissions
 * - Metrics visibility and aggregation level
 * - Resource allocation and scaling behavior
 * - UI presentation and narrative context
 */

export type PersonaMode = 'STEALTH' | 'AUTHORITY' | 'INTERFACE' | 'LAB';

export interface PersonaConfig {
  mode: PersonaMode;
  displayName: string;
  description: string;
  accessLevel: 'admin' | 'operator' | 'user' | 'readonly';
  metricsAccess: MetricsAccess;
  resourceQuota: ResourceQuota;
  allowedEndpoints: string[];
  deniedEndpoints: string[];
}

export interface MetricsAccess {
  aggregateMetrics: boolean;
  slaMetrics: boolean;
  narrativeMetrics: boolean;
  rawMetrics: boolean;
}

export interface ResourceQuota {
  maxConcurrentRequests: number;
  requestsPerMinute: number;
  maxMemoryMB: number;
  maxCpuPercent: number;
}

export interface PersonaContext {
  mode: PersonaMode;
  userId?: string;
  sessionId: string;
  timestamp: Date;
  metadata: Record<string, unknown>;
}

/**
 * Default persona configurations
 */
export const PERSONA_CONFIGS: Record<PersonaMode, PersonaConfig> = {
  STEALTH: {
    mode: 'STEALTH',
    displayName: 'Stealth Mode',
    description: 'Minimal footprint, aggregate-only metrics, covert operation context',
    accessLevel: 'admin',
    metricsAccess: {
      aggregateMetrics: true,
      slaMetrics: false,
      narrativeMetrics: false,
      rawMetrics: false,
    },
    resourceQuota: {
      maxConcurrentRequests: 5,
      requestsPerMinute: 60,
      maxMemoryMB: 512,
      maxCpuPercent: 25,
    },
    allowedEndpoints: ['*'],
    deniedEndpoints: [],
  },
  AUTHORITY: {
    mode: 'AUTHORITY',
    displayName: 'Authority Mode',
    description: 'Full administrative access, SLA-focused metrics, operational command context',
    accessLevel: 'admin',
    metricsAccess: {
      aggregateMetrics: true,
      slaMetrics: true,
      narrativeMetrics: true,
      rawMetrics: true,
    },
    resourceQuota: {
      maxConcurrentRequests: 20,
      requestsPerMinute: 300,
      maxMemoryMB: 2048,
      maxCpuPercent: 80,
    },
    allowedEndpoints: ['*'],
    deniedEndpoints: [],
  },
  INTERFACE: {
    mode: 'INTERFACE',
    displayName: 'Interface Mode',
    description: 'User-facing presentation, narrative metrics, interactive context',
    accessLevel: 'user',
    metricsAccess: {
      aggregateMetrics: false,
      slaMetrics: false,
      narrativeMetrics: true,
      rawMetrics: false,
    },
    resourceQuota: {
      maxConcurrentRequests: 10,
      requestsPerMinute: 120,
      maxMemoryMB: 1024,
      maxCpuPercent: 50,
    },
    allowedEndpoints: ['/api/message', '/api/chat', '/api/status', '/health', '/ready'],
    deniedEndpoints: ['/api/settings', '/api/backup', '/api/scheduler'],
  },
  LAB: {
    mode: 'LAB',
    displayName: 'Lab Mode',
    description: 'Experimental access, raw metrics, development and testing context',
    accessLevel: 'operator',
    metricsAccess: {
      aggregateMetrics: true,
      slaMetrics: true,
      narrativeMetrics: true,
      rawMetrics: true,
    },
    resourceQuota: {
      maxConcurrentRequests: 50,
      requestsPerMinute: 1000,
      maxMemoryMB: 4096,
      maxCpuPercent: 100,
    },
    allowedEndpoints: ['*'],
    deniedEndpoints: [],
  },
};

/**
 * Persona change event handler type
 */
export type PersonaModeChangeHandler = (
  mode: PersonaMode,
  previousMode: PersonaMode | null,
  context: PersonaContext
) => void | Promise<void>;

/**
 * Persona mode change event emitter
 */
class PersonaModeEmitter {
  private handlers: PersonaModeChangeHandler[] = [];
  private currentMode: PersonaMode | null = null;

  onModeChange(handler: PersonaModeChangeHandler): () => void {
    this.handlers.push(handler);
    return () => {
      const index = this.handlers.indexOf(handler);
      if (index > -1) this.handlers.splice(index, 1);
    };
  }

  async setMode(mode: PersonaMode, context: PersonaContext): Promise<void> {
    const previousMode = this.currentMode;
    this.currentMode = mode;

    for (const handler of this.handlers) {
      await handler(mode, previousMode, context);
    }
  }

  getMode(): PersonaMode | null {
    return this.currentMode;
  }
}

export const personaModeEmitter = new PersonaModeEmitter();

/**
 * Express middleware for persona gating
 * Extracts persona mode from headers and attaches to request
 */
export function personaGate(req: any, res: any, next: () => void): void {
  const headerValue = req.headers['x-persona-mode'];
  const persona: PersonaMode = isValidPersonaMode(headerValue) ? headerValue : 'AUTHORITY';

  req.persona = persona;
  req.personaConfig = PERSONA_CONFIGS[persona];
  req.personaContext = {
    mode: persona,
    userId: req.session?.userId,
    sessionId: req.sessionID || generateSessionId(),
    timestamp: new Date(),
    metadata: {},
  } as PersonaContext;

  // Emit mode change event (async, non-blocking)
  personaModeEmitter.setMode(persona, req.personaContext).catch(console.error);

  next();
}

/**
 * Middleware factory for endpoint-level persona access control
 */
export function requirePersona(...allowedModes: PersonaMode[]) {
  return (req: any, res: any, next: () => void): void => {
    const currentMode = req.persona as PersonaMode;

    if (!allowedModes.includes(currentMode)) {
      res.status(403).json({
        error: 'Persona access denied',
        message: `Endpoint requires persona: ${allowedModes.join(' | ')}`,
        currentPersona: currentMode,
      });
      return;
    }

    next();
  };
}

/**
 * Middleware for endpoint access control based on persona config
 */
export function enforcePersonaAccess(req: any, res: any, next: () => void): void {
  const config = req.personaConfig as PersonaConfig;
  const path = req.path;

  // Check denied endpoints first
  if (config.deniedEndpoints.some(pattern => matchEndpoint(path, pattern))) {
    res.status(403).json({
      error: 'Endpoint denied for persona',
      persona: config.mode,
      endpoint: path,
    });
    return;
  }

  // Check allowed endpoints
  const isAllowed = config.allowedEndpoints.some(pattern => matchEndpoint(path, pattern));
  if (!isAllowed) {
    res.status(403).json({
      error: 'Endpoint not allowed for persona',
      persona: config.mode,
      endpoint: path,
    });
    return;
  }

  next();
}

/**
 * Type guard for PersonaMode
 */
export function isValidPersonaMode(value: unknown): value is PersonaMode {
  return typeof value === 'string' && ['STEALTH', 'AUTHORITY', 'INTERFACE', 'LAB'].includes(value);
}

/**
 * Simple endpoint pattern matching
 */
function matchEndpoint(path: string, pattern: string): boolean {
  if (pattern === '*') return true;
  if (pattern.endsWith('*')) {
    return path.startsWith(pattern.slice(0, -1));
  }
  return path === pattern;
}

/**
 * Generate a simple session ID
 */
function generateSessionId(): string {
  return `sess_${Date.now()}_${Math.random().toString(36).substring(2, 11)}`;
}

// Metrics interfaces for persona-specific metric returns
export interface AggregateMetrics {
  type: 'aggregate';
  totalRequests: number;
  averageLatencyMs: number;
  errorRate: number;
  timestamp: Date;
}

export interface SLAMetrics {
  type: 'sla';
  uptime: number;
  p99LatencyMs: number;
  p95LatencyMs: number;
  slaCompliance: number;
  alertsActive: number;
  timestamp: Date;
}

export interface NarrativeMetrics {
  type: 'narrative';
  summary: string;
  healthStatus: 'healthy' | 'degraded' | 'critical';
  userImpact: string;
  recommendations: string[];
  timestamp: Date;
}

export interface RawMetrics {
  type: 'raw';
  requests: RequestMetric[];
  systemMetrics: SystemMetric[];
  timestamp: Date;
}

export interface RequestMetric {
  id: string;
  endpoint: string;
  method: string;
  latencyMs: number;
  statusCode: number;
  persona: PersonaMode;
  timestamp: Date;
}

export interface SystemMetric {
  name: string;
  value: number;
  unit: string;
  labels: Record<string, string>;
  timestamp: Date;
}

export type PersonaMetrics = AggregateMetrics | SLAMetrics | NarrativeMetrics | RawMetrics;
