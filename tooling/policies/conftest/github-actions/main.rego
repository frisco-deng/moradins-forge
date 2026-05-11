package github_actions

deny contains msg if {
  not input.permissions
  msg := "workflow must declare top-level permissions"
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
