"""
Copyright ©2024. The Regents of the University of California (Regents). All Rights Reserved.

Permission to use, copy, modify, and distribute this software and its documentation
for educational, research, and not-for-profit purposes, without fee and without a
signed licensing agreement, is hereby granted, provided that the above copyright
notice, this paragraph and the following two paragraphs appear in all copies,
modifications, and distributions.

Contact The Office of Technology Licensing, UC Berkeley, 2150 Shattuck Avenue,
Suite 510, Berkeley, CA 94720-1620, (510) 643-7201, otl@berkeley.edu,
http://ipira.berkeley.edu/industry-info for commercial licensing opportunities.

IN NO EVENT SHALL REGENTS BE LIABLE TO ANY PARTY FOR DIRECT, INDIRECT, SPECIAL,
INCIDENTAL, OR CONSEQUENTIAL DAMAGES, INCLUDING LOST PROFITS, ARISING OUT OF
THE USE OF THIS SOFTWARE AND ITS DOCUMENTATION, EVEN IF REGENTS HAS BEEN ADVISED
OF THE POSSIBILITY OF SUCH DAMAGE.

REGENTS SPECIFICALLY DISCLAIMS ANY WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE. THE
SOFTWARE AND ACCOMPANYING DOCUMENTATION, IF ANY, PROVIDED HEREUNDER IS PROVIDED
"AS IS". REGENTS HAS NO OBLIGATION TO PROVIDE MAINTENANCE, SUPPORT, UPDATES,
ENHANCEMENTS, OR MODIFICATIONS.
"""

from datetime import datetime, timezone
import time

from flask import current_app as app
from nessie.externals import canvas_data_2, dynamodb
from nessie.jobs.background_job import BackgroundJob


"""Logic to trigger query Canvas Data 2 snapshot job with Instructure."""


class TriggerCD2QueryJobs(BackgroundJob):

    @classmethod
    def generate_job_id(cls):
        return 'TriggerCD2QueryJobs_' + str(int(time.time()))

    def insert_cd2_metadata(self, namespace, table_query_jobs, nessie_job_id):
        try:
            # Use DynamoDB resource instead of client
            dynamodb_resource = dynamodb.get_client()
            # logger.info(f'{dynamodb_resource}')
            environment_name = 'prod'  # You could also fetch this from os.environ if needed.

            # Change table name dynamically as needed
            table = dynamodb_resource.Table(app.config['CD2_DYNAMODB_METADATA_TABLE'])

            # Insert the item into DynamoDB
            response = table.put_item(
                Item={
                    'cd2_query_job_id': nessie_job_id,
                    'created_at': datetime.now(timezone.utc).isoformat(),
                    'namespace': namespace,
                    'workflow_status': 'table_query_job_triggered',
                    'updated_at': datetime.now(timezone.utc).isoformat(),
                    'environment': environment_name,
                    'table_query_jobs_id': table_query_jobs,
                    'snapshot_objects': [],
                },
            )

            app.logger.info('CD2 metadata updated successfully in DynamoDB', response)
            return True

        except Exception as e:
            app.logger.error(f'Error inserting CD2 metadata into DynamoDB: {str(e)}')
            return False

    def run(self, cleanup=True):
        nessie_job_id = self.generate_job_id()
        app.logger.info(f'Starting Query Canvas Data 2 snapshot job... (id={nessie_job_id})')
        namespace = 'canvas'
        cd2_tables = canvas_data_2.get_cd2_tables_list(namespace)

        app.logger.info(f'{len(cd2_tables)} tables available for download from namespace {namespace}. \n{cd2_tables}')
        app.logger.info('Begin query snapshot process for each table and retrieve job ids for tracking')
        cd2_table_query_jobs = []
        cd2_table_query_jobs = canvas_data_2.start_query_snapshot(cd2_tables)

        app.logger.info(f'Started query snapshot jobs and retrived job IDs for {len(cd2_table_query_jobs)} Canvas data 2 tables')

        status = self.insert_cd2_metadata(namespace, cd2_table_query_jobs, nessie_job_id)

        if status is False:
            return ('Inserting CD2 job metadata failed.')
        else:
            return ('Triggered Query snapshot Jobs on Canvas Data DAP API successfully. Inserted job metadata on DynamoDB tables for tracking')
