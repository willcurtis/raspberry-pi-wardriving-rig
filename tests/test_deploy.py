from pathlib import Path
import unittest


DEPLOY = (Path(__file__).parents[1] / "deploy.sh").read_text(encoding="utf-8")


class DeployTests(unittest.TestCase):
    def test_configures_predictable_mdns_hostname(self):
        self.assertIn("DEVICE_HOSTNAME=wardriver", DEPLOY)
        self.assertIn('hostnamectl set-hostname "$DEVICE_HOSTNAME"', DEPLOY)
        self.assertIn("avahi-daemon", DEPLOY)
        self.assertIn("systemctl enable --now avahi-daemon.service", DEPLOY)

    def test_reports_mdns_dashboard_url(self):
        self.assertIn(
            'echo "Dashboard: http://${DEVICE_HOSTNAME}.local:8080"', DEPLOY
        )

    def test_installs_restricted_remote_control_permissions(self):
        self.assertIn(
            "systemctl kill --signal=SIGKILL wardrive-kismet.service", DEPLOY
        )
        self.assertIn(
            "systemctl restart gpsd.socket gpsd.service", DEPLOY
        )
        self.assertIn(
            "systemctl restart avahi-daemon.service", DEPLOY
        )


if __name__ == "__main__":
    unittest.main()
