import asyncio
import os
import sys

import streamlit as st
from dotenv import load_dotenv

load_dotenv()
st.set_page_config(page_title="AutoGen Task Runner", layout="wide")

AUTOGEN_SETUP_AVAILABLE = False
team = None
setup_file_path = os.path.join(os.path.dirname(__file__), 'autogen_setup.py')
if not os.path.exists(setup_file_path):
    st.error(f"Error: 'autogen_setup.py' not found.")
else:
    try:
        from autogen_setup import team as ag_team
        from autogen_agentchat.base import TaskResult

        if ag_team:
            team = ag_team
            AUTOGEN_SETUP_AVAILABLE = True
        else:
            st.error("Error: 'team' object not created in 'autogen_setup.py'.")
    except Exception as e_init:
        st.error(f"An unexpected error occurred during initial setup: {e_init}")

st.title("Ask the AutoGen Team (Developer & Reviewer)")
st.sidebar.header("About")
st.sidebar.info("Enter task, run, view result. Check 'Show Logs' for details.")
user_task_input = st.text_area("Enter task:", height=100, key="task_input_area", disabled=not AUTOGEN_SETUP_AVAILABLE)
show_logs_checkbox = st.checkbox("Show Logs", key="show_logs", value=False)
run_button = st.button("Run Task", disabled=not AUTOGEN_SETUP_AVAILABLE)
st.markdown("---")

if 'final_response_text' not in st.session_state: st.session_state['final_response_text'] = ""
if 'stop_reason_text' not in st.session_state: st.session_state['stop_reason_text'] = ""
if 'final_source_text' not in st.session_state: st.session_state['final_source_text'] = ""
if 'conversation_log_list' not in st.session_state: st.session_state['conversation_log_list'] = []
if 'last_run_error' not in st.session_state: st.session_state['last_run_error'] = None

tab1, tab2 = st.tabs(["Final Result", "Conversation Log"])
with tab1:
    st.subheader("Final Agent Response:")
    st.text_area("Output:", value=st.session_state['final_response_text'], height=300, key="output_area", disabled=True)
    if st.session_state['final_source_text']:
        st.caption(
            f"Source: {st.session_state['final_source_text']} | Stop Reason: {st.session_state['stop_reason_text']}")
    elif st.session_state['last_run_error']:
        st.error(f"Last run failed: {st.session_state['last_run_error']}")
    elif not st.session_state['final_response_text']:
        st.caption("Run a task to see the result.")

with tab2:
    st.subheader("Agent Conversation Log")
    if show_logs_checkbox:
        if st.session_state['conversation_log_list']:
            for entry in st.session_state['conversation_log_list']:
                st.markdown(entry, unsafe_allow_html=True)
                st.markdown("---")
        elif st.session_state['last_run_error']:
            st.warning("Run failed, log incomplete.")
            st.error(st.session_state['last_run_error'])
        else:
            st.info("No log available.")
    else:
        st.info("Check 'Show Logs' to view details.")


async def run_autogen_stream(task: str, team_instance):
    conversation_log_entries = []
    last_agent_message_object = None
    previous_agent_message_object = None
    final_message_to_display = None
    stop_reason = "Unknown"
    final_agent_name = "Unknown"
    is_task_result = False

    await team_instance.reset()

    async for message in team_instance.run_stream(task=task):
        log_entry = ""
        source_name = getattr(message, 'source', getattr(message, 'name', 'System'))
        is_agent_message_with_content = False

        if hasattr(message, 'stop_reason'):
            is_task_result = True
            message_stop_reason = getattr(message, 'stop_reason', "Unknown")
            log_entry = f"**System:** Task finished. Stop Reason: {message_stop_reason}"
            stop_reason = message_stop_reason or "Completed"

        elif hasattr(message, 'content'):
            is_agent_source = source_name not in ['user', 'System', 'UserProxyAgent']
            if is_agent_source:
                is_agent_message_with_content = True

            message_content = getattr(message, 'content')
            if isinstance(message_content, str):
                escaped_content = message_content.replace("<", "<").replace(">", ">")
                log_entry = f"**{source_name}:**\n```\n{escaped_content}\n```" if "```" in escaped_content else f"**{source_name}:**\n{escaped_content}"
            elif message_content is not None:
                log_entry = f"**{source_name}:** `({type(message_content).__name__} content)`"
            else:
                role = getattr(message, 'role', None)
                log_entry = f"**{source_name}:** `(Role: {role} - Content is None)`"

        else:
            event_type_name = type(message).__name__
            log_entry = f"**{source_name}:** `({event_type_name})`"

        if log_entry:
            conversation_log_entries.append(log_entry)

        if is_agent_message_with_content:
            previous_agent_message_object = last_agent_message_object
            last_agent_message_object = message

        if is_task_result:
            break

    lgtm_termination_occurred = "LGTM received" in stop_reason

    if lgtm_termination_occurred and previous_agent_message_object:
        final_message_to_display = previous_agent_message_object
        # print("DEBUG: Using PREVIOUS message for final output due to LGTM stop.")
    elif last_agent_message_object:
        final_message_to_display = last_agent_message_object
        # print("DEBUG: Using LAST message for final output.")
    # else:
    # print("DEBUG: No suitable agent message found for final output.")

    if final_message_to_display:
        final_content_raw = getattr(final_message_to_display, 'content', '[No content found in selected message]')
        final_agent_message_content = str(final_content_raw) if not isinstance(final_content_raw,
                                                                               str) else final_content_raw
        final_agent_name = getattr(final_message_to_display, 'source',
                                   getattr(final_message_to_display, 'name', 'Unknown'))
    else:
        final_agent_message_content = "[No agent response recorded before termination]"
        if is_task_result:
            final_agent_name = "System"

    # print(f"DEBUG: Final display content: {final_agent_message_content[:50]}...")
    # print(f"DEBUG: Final display source: {final_agent_name}")
    # print(f"DEBUG: Stop Reason: {stop_reason}")

    return conversation_log_entries, final_agent_message_content, final_agent_name, stop_reason


if run_button and user_task_input and AUTOGEN_SETUP_AVAILABLE and team:
    with st.spinner('Agents are working... Please wait.'):
        try:
            loop = asyncio.get_event_loop()
            if loop.is_closed():
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        try:
            st.session_state['conversation_log_list'] = []
            st.session_state['final_response_text'] = ""
            st.session_state['stop_reason_text'] = ""
            st.session_state['final_source_text'] = ""
            st.session_state['last_run_error'] = None

            log_list, final_text, final_source, stop_reason_val = loop.run_until_complete(
                run_autogen_stream(user_task_input, team)
            )

            st.session_state['conversation_log_list'] = log_list
            st.session_state['final_response_text'] = final_text
            st.session_state['stop_reason_text'] = stop_reason_val
            st.session_state['final_source_text'] = final_source

        except Exception as e:
            error_msg = f"An error occurred during the AutoGen run: {type(e).__name__} - {e}"
            st.session_state['last_run_error'] = error_msg
            print(f"Error during run: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc()

        st.rerun()
