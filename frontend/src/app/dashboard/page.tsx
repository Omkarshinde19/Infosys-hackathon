import { Alerts } from "@/components/dashboard/Alerts";
import { Diagnosis } from "@/components/dashboard/Diagnosis";
import { FaultLab } from "@/components/dashboard/FaultLab";
import { LiveChart } from "@/components/dashboard/LiveChart";
import { NetworkView } from "@/components/dashboard/NetworkView";
import { Overview } from "@/components/dashboard/Overview";
import { Section } from "@/components/dashboard/Section";

export default function ControlRoom() {
  return (
    <div className="mx-auto flex max-w-7xl flex-col gap-16 pb-24">
      <header className="pt-2">
        <p className="text-sm text-fg-muted">Control Room</p>
        <h1 className="text-4xl font-semibold tracking-tight">Campus network, live</h1>
      </header>

      <Section id="overview" title="Overview" subtitle="How the whole network is doing right now.">
        <Overview />
      </Section>

      <Section id="alerts" title="Alerts" subtitle="Problems the detector has noticed. Several detectors must agree before an alert is raised.">
        <Alerts />
      </Section>

      <Section id="diagnosis" title="Diagnosis" subtitle="The single most likely root cause behind the alerts, with the evidence.">
        <Diagnosis />
      </Section>

      <Section id="network" title="Network" subtitle="Every device and connection, coloured by health. Switch to 3D to explore the layers.">
        <NetworkView />
      </Section>

      <Section id="telemetry" title="Telemetry" subtitle="Latency and packet loss for every traffic flow, updated twice a second.">
        <div className="grid gap-4">
          <LiveChart title="Latency per flow" metric="latency_ms" unit="ms" />
          <LiveChart title="Packet loss per flow" metric="loss_pct" unit="%" />
        </div>
      </Section>

      <Section id="faults" title="Fault Lab" subtitle="Safely break the simulated network and watch what happens.">
        <FaultLab />
      </Section>
    </div>
  );
}
