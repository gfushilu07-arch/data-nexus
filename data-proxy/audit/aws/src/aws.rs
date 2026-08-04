// Copyright 2022 SphereEx Authors
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
//     http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

use aws_config::meta::region::RegionProviderChain;
use aws_sdk_cloudwatchlogs::{
    model::{InputLogEvent, LogStream},
    Client,
};
use chrono::Utc;
use tracing::trace;

pub struct CloudWatchLog {
    log_group_name: String,
    log_stream_name: String,
    timestamp: i64,
    message: String,
}

impl CloudWatchLog {
    pub fn new(group: String, stream: String, message: String) -> Self {
        let now = Utc::now();
        CloudWatchLog {
            log_group_name: group,
            log_stream_name: stream,
            timestamp: now.timestamp_millis(),
            message,
        }
    }
}

pub struct CloudWatchSinker {
    pub client: Client,
}

impl CloudWatchSinker {
    pub async fn new() -> Self {
        let region_provider = RegionProviderChain::first_try("us-east-1");
        let shared_config = aws_config::from_env().region(region_provider).load().await;
        let client = Client::new(&shared_config);

        CloudWatchSinker { client }
    }
    pub async fn send(&self, input: CloudWatchLog) -> Result<(), aws_sdk_cloudwatchlogs::Error> {
        let log_group_name = input.log_group_name.clone();
        let log_stream_name = input.log_stream_name.clone();
        let message = input.message.clone();

        let streams =
            self.client.describe_log_streams().log_group_name(input.log_group_name).send().await?;
        if let Some(stream) =
            find_log_stream(streams.log_streams().unwrap_or(&[]), &log_stream_name)
        {
            let builder = InputLogEvent::builder();
            let e = builder
                .set_message(Some(message.clone()))
                .set_timestamp(Some(input.timestamp))
                .build();

            let resp = self
                .client
                .put_log_events()
                .set_sequence_token(stream.upload_sequence_token().map(str::to_owned))
                .log_group_name(log_group_name.clone())
                .log_stream_name(log_stream_name)
                .log_events(e)
                .send()
                .await?;
            trace!("aws resp {:?}", resp);
        }
        Ok(())
    }
}

fn find_log_stream<'a>(streams: &'a [LogStream], name: &str) -> Option<&'a LogStream> {
    streams.iter().find(|stream| stream.log_stream_name() == Some(name))
}

#[cfg(test)]
mod tests {
    use super::find_log_stream;
    use aws_sdk_cloudwatchlogs::model::LogStream;

    #[test]
    fn find_log_stream_handles_empty_and_malformed_entries() {
        let streams = vec![
            LogStream::builder().build(),
            LogStream::builder().log_stream_name("target").build(),
        ];

        assert!(find_log_stream(&[], "target").is_none());
        assert_eq!(
            find_log_stream(&streams, "target").and_then(LogStream::upload_sequence_token),
            None
        );
        assert!(find_log_stream(&streams, "missing").is_none());
    }

    #[test]
    fn find_log_stream_preserves_sequence_token() {
        let streams = vec![LogStream::builder()
            .log_stream_name("target")
            .upload_sequence_token("sequence-1")
            .build()];

        assert_eq!(
            find_log_stream(&streams, "target").and_then(LogStream::upload_sequence_token),
            Some("sequence-1")
        );
    }
}
