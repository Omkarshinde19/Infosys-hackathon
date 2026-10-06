# NetHeal healing guardrails (OPA Rego). Evaluated in-process with regopy for every
# candidate fix, after its digital-twin dry run. Any `deny` message blocks the fix.
package netheal.healing

import rego.v1

max_link_util := 0.85
healthy_loss_pct := 1.0
max_flows_moved := 5
max_actions_per_minute := 3

deny contains msg if {
	input.prediction.loss_pct >= healthy_loss_pct
	msg := sprintf("Doesn't restore the traffic: twin predicts %.1f%% loss", [input.prediction.loss_pct])
}

deny contains msg if {
	input.prediction.max_util > max_link_util
	msg := sprintf("Would push a link to %.0f%% load (limit %.0f%%)", [input.prediction.max_util * 100, max_link_util * 100])
}

deny contains msg if {
	input.prediction.other_loss_pct >= healthy_loss_pct
	msg := sprintf("Would hurt other traffic: %.1f%% loss on an unaffected flow", [input.prediction.other_loss_pct])
}

deny contains msg if {
	count(input.action.flows_moved) > max_flows_moved
	msg := sprintf("Moves %d flows at once (limit %d)", [count(input.action.flows_moved), max_flows_moved])
}

deny contains msg if {
	input.action.type == "drain_node"
	input.action.target_layer == "core"
	msg := "Never drains a core router automatically: blast radius is the whole campus"
}

deny contains msg if {
	input.actions_last_minute >= max_actions_per_minute
	msg := sprintf("Rate limit: already %d automatic changes in the last minute", [input.actions_last_minute])
}

allow if count(deny) == 0
