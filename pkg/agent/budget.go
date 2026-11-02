package agent

type Budget struct {
	MaxTurns int
	Current  int
}

func CheckBudget(b *Budget, max int) bool {
	if max > 0 && b.Current >= max {
		return false
	}
	b.Current++
	return true
}
