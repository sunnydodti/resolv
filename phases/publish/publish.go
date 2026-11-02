package phases

import "resolv/pkg/platform"

func Publish() error {
	return platform.OpenPullRequest("Resolv fix", "Auto PR", true)
}
