import assert from 'node:assert/strict';

const REQUIRED_ANNOTATIONS = {
  readOnlyHint: true,
  destructiveHint: false,
  idempotentHint: true,
  openWorldHint: false
};

function isRecord(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function qualifyStatusContract(tool, issues) {
  const input = tool.inputSchema;
  if (!isRecord(input) || input.type !== 'object') {
    issues.push('service_status.inputSchema must be an object schema');
  } else {
    const label = isRecord(input.properties) ? input.properties.label : undefined;
    if (!isRecord(label) || label.type !== 'string') {
      issues.push('service_status.inputSchema.properties.label must be a string');
    } else if (label.maxLength !== 80) {
      issues.push('service_status.inputSchema.properties.label.maxLength must be 80');
    }
    if (Array.isArray(input.required) && input.required.includes('label')) {
      issues.push('service_status.inputSchema.label must stay optional');
    }
  }

  const output = tool.outputSchema;
  if (!isRecord(output) || output.type !== 'object') {
    issues.push('service_status.outputSchema must be an object schema');
  } else {
    const properties = isRecord(output.properties) ? output.properties : {};
    if (!isRecord(properties.status) || properties.status.const !== 'ready') {
      issues.push('service_status.outputSchema.properties.status must be the literal "ready"');
    }
    if (!isRecord(properties.service) || properties.service.type !== 'string') {
      issues.push('service_status.outputSchema.properties.service must be a string');
    }
    if (!isRecord(properties.label) || properties.label.type !== 'string') {
      issues.push('service_status.outputSchema.properties.label must be a string');
    }
    const required = Array.isArray(output.required) ? output.required : [];
    for (const field of ['status', 'service']) {
      if (!required.includes(field)) {
        issues.push(`service_status.outputSchema.required must include ${field}`);
      }
    }
    if (required.includes('label')) {
      issues.push('service_status.outputSchema.label must stay optional');
    }
    if (output.additionalProperties !== false) {
      issues.push('service_status.outputSchema.additionalProperties must be false');
    }
  }

  const annotations = tool.annotations;
  for (const [key, expected] of Object.entries(REQUIRED_ANNOTATIONS)) {
    if (!isRecord(annotations) || annotations[key] !== expected) {
      issues.push(`service_status.annotations.${key} must be ${expected}`);
    }
  }
}

/**
 * Validate an actual tools/list result without assuming that service_status is
 * the only tool or the first one. Additional generated tools are legal; the
 * fixed status contract, unique non-empty names and its schema/annotations are
 * not optional.
 */
export function qualifyToolDiscovery(tools) {
  const issues = [];
  if (!Array.isArray(tools)) {
    issues.push('tools/list result must be an array');
    return issues;
  }

  const names = new Set();
  tools.forEach((tool, index) => {
    const path = `tools[${index}]`;
    if (!isRecord(tool)) {
      issues.push(`${path} must be a tool object`);
      return;
    }
    const { name } = tool;
    if (typeof name !== 'string' || name.trim().length === 0) {
      issues.push(`${path}.name must be a non-empty string`);
      return;
    }
    if (names.has(name)) {
      issues.push(`${path}.name "${name}" duplicates an earlier tool name`);
    }
    names.add(name);
  });

  const statusTools = tools.filter(tool => isRecord(tool) && tool.name === 'service_status');
  if (statusTools.length === 0) {
    issues.push('service_status is required but was not discovered');
  } else if (statusTools.length > 1) {
    issues.push(`service_status must be registered exactly once; found ${statusTools.length}`);
  } else {
    qualifyStatusContract(statusTools[0], issues);
  }

  return issues;
}

export function assertQualifiedDiscovery(tools, label = 'MCP discovery') {
  const issues = qualifyToolDiscovery(tools);
  assert.deepEqual(issues, [], `${label} failed:\n- ${issues.join('\n- ')}`);
  return tools;
}
