Feature: Chart tgz only submission
    Partners or redhat associates can publish their chart by submitting
    error-free chart in tgz format without the report.

    Scenario: The partner hashicorp submits a error-free chart tgz for vault
        Given hashicorp is a valid partner
        And hashicorp has created an error-free chart tgz for vault
        When hashicorp sends a pull request with the vault tgz chart
        Then hashicorp sees the pull request is merged
        And the index.yaml file is updated with an entry for the submitted chart
        And a release for the vault chart is published with corresponding report and chart tarball

    Scenario: A redhat associate submits a error-free chart tgz for vault
        Given a redhat associate has a valid identity
        And the redhat associate has created an error-free chart tgz for vault
        When the redhat associate sends a pull request with the vault tgz chart
        Then the redhat associate sees the pull request is merged
        And the index.yaml file is updated with an entry for the submitted chart
        And a release for the vault chart is published with corresponding report and chart tarball
