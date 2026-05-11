package kubernetes

default containers := []

containers := input.spec.template.spec.containers if {
  input.kind == "Deployment"
}

containers := input.spec.template.spec.containers if {
  input.kind == "StatefulSet"
}

containers := input.spec.template.spec.containers if {
  input.kind == "DaemonSet"
}

containers := input.spec.template.spec.containers if {
  input.kind == "Job"
}

containers := input.spec.jobTemplate.spec.template.spec.containers if {
  input.kind == "CronJob"
}

deny contains msg if {
  some idx
  container := containers[idx]
  container.securityContext.privileged == true
  msg := sprintf("container %s must not run privileged", [container.name])
}

deny contains msg if {
  some idx
  container := containers[idx]
  not container.resources.requests
  msg := sprintf("container %s must declare resource requests", [container.name])
}

deny contains msg if {
  some idx
  container := containers[idx]
  not container.resources.limits
  msg := sprintf("container %s must declare resource limits", [container.name])
}
