package cl.uchile.pmd;

import org.apache.giraph.graph.BasicComputation;
import org.apache.giraph.graph.Vertex;
import org.apache.giraph.edge.Edge;
import org.apache.hadoop.io.DoubleWritable;
import org.apache.hadoop.io.FloatWritable;
import org.apache.hadoop.io.LongWritable;
import java.io.IOException;

/**
 * WeightedPageRankJsonComputation - CC5212 Procesamiento Masivo de Datos (Grupo 13)
 * Compatible 100% con JsonLongDoubleFloatDoubleVertexInputFormat del Laboratorio 8:
 *   [vertex_id, vertex_value, [[dest_id, edge_weight], ...]]
 */
public class WeightedPageRankJsonComputation extends BasicComputation<
    LongWritable, DoubleWritable, FloatWritable, DoubleWritable> {

    public static final int MAX_SUPERSTEPS = 30;
    public static final double DAMPING = 0.85;

    @Override
    public void compute(
            Vertex<LongWritable, DoubleWritable, FloatWritable> vertex,
            Iterable<DoubleWritable> messages) throws IOException {

        if (getSuperstep() >= 1) {
            double sum = 0.0;
            for (DoubleWritable msg : messages) {
                sum += msg.get();
            }
            double rank = ((1.0 - DAMPING) / getTotalNumVertices()) + (DAMPING * sum);
            vertex.setValue(new DoubleWritable(rank));
        }

        if (getSuperstep() < MAX_SUPERSTEPS) {
            double totalWeight = 0.0;
            for (Edge<LongWritable, FloatWritable> edge : vertex.getEdges()) {
                totalWeight += edge.getValue().get();
            }
            if (totalWeight > 0.0) {
                double currentRank = vertex.getValue().get();
                for (Edge<LongWritable, FloatWritable> edge : vertex.getEdges()) {
                    double w = edge.getValue().get();
                    sendMessage(edge.getTargetVertexId(),
                                new DoubleWritable(currentRank * (w / totalWeight)));
                }
            }
        } else {
            vertex.voteToHalt();
        }
    }
}
