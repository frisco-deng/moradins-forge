package github_actions

deny contains msg if {
  not input.permissions
  msg := "workflow must declare top-level permissions"
}

deny contains msg if {
  not input.concurrency
  msg := "workflow must declare top-level concurrency"
}

deny contains msg if {
  some job_name
  job := input.jobs[job_name]
  not job.permissions
  msg := sprintf("job %s must declare explicit permissions", [job_name])
}

deny contains msg if {
  some job_name
  job := input.jobs[job_name]
  some step in job.steps
  ref := step.uses
  endswith(ref, "@main")
  msg := sprintf("job %s uses an action pinned to @main", [job_name])
}

deny contains msg if {
  some job_name
  job := input.jobs[job_name]
  some step in job.steps
  ref := step.uses
  endswith(ref, "@master")
  msg := sprintf("job %s uses an action pinned to @master", [job_name])
}

deny contains msg if {
  some job_name
  job := input.jobs[job_name]
  some step in job.steps
  ref := step.uses
  is_string(ref)
  not startswith(ref, "./")
  not regex.match("^.+@[0-9a-fA-F]{40}$", ref)
  msg := sprintf("job %s uses an action without a pinned 40-character SHA: %s", [job_name, ref])
}

deny contains msg if {
  some job_name
  job := input.jobs[job_name]
  some step in job.steps
  ref := step.uses
  is_string(ref)
  contains(ref, "actions/checkout@")
  not checkout_persist_credentials_disabled(step)
  msg := sprintf("job %s checkout must set persist-credentials false", [job_name])
}

deny contains msg if {
  has_pull_request_target
  msg := "pull_request_target requires explicit policy allowlist"
}

has_pull_request_target if {
  object.get(object.get(input, "on", {}), "pull_request_target", "__missing__") != "__missing__"
}

has_pull_request_target if {
  object.get(object.get(input, "true", {}), "pull_request_target", "__missing__") != "__missing__"
}

checkout_persist_credentials_disabled(step) if {
  step["with"]["persist-credentials"] == false
}

checkout_persist_credentials_disabled(step) if {
  lower(sprintf("%v", [step["with"]["persist-credentials"]])) == "false"
}
