# --- tools/network_analysis.py ---
import logging
from scapy.all import rdpcap, PcapReader, IP, TCP, UDP, Ether
from datetime import datetime

logger = logging.getLogger(__name__)

def analyze_pcap(pcap_path):
    """
    Analyzes a PCAP file to extract basic info and conversations.

    Args:
        pcap_path (str): Path to the PCAP file.

    Returns:
        dict: A dictionary containing analysis results:
              {'summary': {'packet_count': int, 'start_time': str, 'end_time': str, 'error': str or None},
               'conversations': list of dicts [{'protocol': str, 'src_ip': str, 'src_port': int/str,
                                                'dst_ip': str, 'dst_port': int/str, 'packet_count': int}]
              }
              Returns {'summary': {'error': message}, 'conversations': []} on failure.
    """
    summary = {'packet_count': 0, 'start_time': None, 'end_time': None, 'error': None}
    conversations = {}  # Use dict to aggregate counts: key -> count
    processed_count = 0

    try:
        logger.info(f"Starting PCAP analysis for: {pcap_path}")

        # Use PcapReader for potentially large files to avoid loading all into memory
        with PcapReader(pcap_path) as pcap_reader:
            for packet in pcap_reader:
                processed_count += 1
                timestamp = float(packet.time)

                # Update summary times
                if summary['start_time'] is None or timestamp < summary['start_time']:
                    summary['start_time'] = timestamp
                if summary['end_time'] is None or timestamp > summary['end_time']:
                    summary['end_time'] = timestamp

                # Extract conversation info (focus on IP/TCP/UDP)
                if IP in packet:
                    src_ip = packet[IP].src
                    dst_ip = packet[IP].dst
                    protocol = packet[IP].proto # Protocol number

                    src_port = 'N/A'
                    dst_port = 'N/A'
                    proto_name = 'IP' # Default

                    if TCP in packet:
                        src_port = packet[TCP].sport
                        dst_port = packet[TCP].dport
                        proto_name = 'TCP'
                    elif UDP in packet:
                        src_port = packet[UDP].sport
                        dst_port = packet[UDP].dport
                        proto_name = 'UDP'
                    # Add more protocols (ICMP etc.) if needed

                    # Normalize conversation tuple (lowest IP/Port first) to count both directions
                    if (src_ip, src_port) > (dst_ip, dst_port):
                        conv_key = (proto_name, dst_ip, dst_port, src_ip, src_port)
                    else:
                        conv_key = (proto_name, src_ip, src_port, dst_ip, dst_port)

                    conversations[conv_key] = conversations.get(conv_key, 0) + 1

                elif Ether in packet:
                     # Could add Ethernet-level conversation tracking if needed
                     pass

                # Add progress reporting here if needed (e.g., every N packets)
                # if processed_count % 1000 == 0:
                #     logger.debug(f"Processed {processed_count} packets...")

        summary['packet_count'] = processed_count

        # Format timestamps
        summary['start_time'] = datetime.fromtimestamp(summary['start_time']).strftime('%Y-%m-%d %H:%M:%S') if summary['start_time'] else "N/A"
        summary['end_time'] = datetime.fromtimestamp(summary['end_time']).strftime('%Y-%m-%d %H:%M:%S') if summary['end_time'] else "N/A"

        # Convert conversation dict to list of dicts for display
        conv_list = []
        for key, count in conversations.items():
            conv_list.append({
                'protocol': key[0],
                'src_ip': key[1],
                'src_port': key[2],
                'dst_ip': key[3],
                'dst_port': key[4],
                'packet_count': count
            })

        # Sort conversations, e.g., by packet count descending
        conv_list.sort(key=lambda x: x['packet_count'], reverse=True)

        logger.info(f"Finished PCAP analysis for: {pcap_path}. Found {len(conv_list)} conversations.")
        return {'summary': summary, 'conversations': conv_list}

    except FileNotFoundError:
        errmsg = f"PCAP file not found: {pcap_path}"
        logger.error(errmsg)
        summary['error'] = errmsg
        return {'summary': summary, 'conversations': []}
    except Exception as e:
        errmsg = f"Error analyzing PCAP {pcap_path}: {e}"
        logger.error(errmsg, exc_info=True)
        summary['error'] = errmsg
        # Return partial results if possible
        summary['packet_count'] = processed_count
        summary['start_time'] = datetime.fromtimestamp(summary['start_time']).strftime('%Y-%m-%d %H:%M:%S') if summary.get('start_time') else "Error"
        summary['end_time'] = datetime.fromtimestamp(summary['end_time']).strftime('%Y-%m-%d %H:%M:%S') if summary.get('end_time') else "Error"
        return {'summary': summary, 'conversations': []} # Don't return potentially incomplete conversations