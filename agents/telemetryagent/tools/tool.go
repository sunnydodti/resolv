package tools

import "resolv/pkg/pipeline"

func WriteAuditLog(sessionData string) error { return pipeline.WriteAuditLog(sessionData) }
