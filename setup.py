from setuptools import setup

plugin_identifier = "bambuboard"
plugin_package = "octoprint_bambuboard"
plugin_name = "OctoPrint-BambuBoard"
plugin_version = "0.1.0"
plugin_description = "Multi-printer Bambu Lab dashboard for OctoPrint. Manage multiple Bambu Lab printers from a single OctoPrint instance with real-time MQTT monitoring, print controls, AMS management, and file operations."
plugin_author = "Tim Schwarz"
plugin_author_email = "schwarztim@users.noreply.github.com"
plugin_url = "https://github.com/schwarztim/OctoPrint-BambuBoard"
plugin_license = "AGPLv3"
plugin_additional_data = []

plugin_requires = ["bambu-printer-manager>=0.5.4"]
plugin_extra_requires = {}
plugin_additional_packages = []
plugin_ignored_packages = []

additional_setup_parameters = {
    "python_requires": ">=3.7,<4",
}

try:
    import octoprint_setuptools
except ImportError:
    import sys
    print(
        "Could not import OctoPrint's setuptools, are you sure you are running that "
        "under the same python installation that OctoPrint is installed under?"
    )
    sys.exit(-1)

setup_parameters = octoprint_setuptools.create_plugin_setup_parameters(
    identifier=plugin_identifier,
    package=plugin_package,
    name=plugin_name,
    version=plugin_version,
    description=plugin_description,
    author=plugin_author,
    mail=plugin_author_email,
    url=plugin_url,
    license=plugin_license,
    requires=plugin_requires,
    extra_requires=plugin_extra_requires,
    additional_packages=plugin_additional_packages,
    ignored_packages=plugin_ignored_packages,
    additional_data=plugin_additional_data,
)

if len(googled := additional_setup_parameters):
    setup_parameters.update(googled)

setup(**setup_parameters)
