package compose

deny contains msg if {
  some name
  service := input.services[name]
  service.privileged == true
  msg := sprintf("service %s must not run privileged", [name])
}

deny contains msg if {
  some name
  service := input.services[name]
  image := service.image
  endswith(image, ":latest")
  msg := sprintf("service %s uses a latest image tag", [name])
}

deny contains msg if {
  some name
  service := input.services[name]
  not service.healthcheck
  msg := sprintf("service %s must declare a healthcheck", [name])
}
