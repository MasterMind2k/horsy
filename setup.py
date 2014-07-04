from setuptools import setup, find_packages

setup(
  name = "Horsy",
  version = "0.1",
  packages = find_packages(),
# TODO dependencies
#  install_requires = [""],

  author = "Gregor Kalisnik",
  author_email = "gregor@unimatrix.si",
  description = "Horsy, the Object-Document Mapper.",
  license = "BSD",
  keywords = "mongodb elasticsearch odm mapper"
)
